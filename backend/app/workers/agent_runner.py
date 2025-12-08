"""
Agent Runner Worker - Dramatiq Task Execution

This worker orchestrates the agent workflow pipeline.
It picks up tasks from the queue and executes:
    Task Creation → Planning → State Update → Agent Dispatch

Key Responsibilities:
1. Load Task and Repository from database
2. Initialize LLMClient and ProjectMap (RAG context)
3. Dispatch PlannerAgent to create TaskPlan
4. Log all agent outputs to AgentLog table (SSE streaming source)
5. Transition task state based on confidence score
6. Handle errors gracefully with proper logging
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure libs directory is in python path for gravity_core imports
# This assumes the worker is running from project root or similar structure
project_root = Path(__file__).resolve().parent.parent.parent.parent
libs_path = project_root / "libs"
if str(libs_path) not in sys.path:
    sys.path.append(str(libs_path))

import asyncio
import json
import traceback
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from uuid import UUID

import dramatiq
import structlog
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Broker and Session Configuration
# =============================================================================

# Configure Redis broker for Dramatiq
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)


# =============================================================================
# Utility Functions
# =============================================================================


async def log_agent_output(
    session: AsyncSession,
    task_id: UUID,
    agent_output,
    step_number: int = 0,
) -> None:
    """
    Insert an AgentOutput into the AgentLog table.

    This is the explainability trigger - every agent action is logged
    with both technical details and user-facing explanations.

    CRITICAL: This provides the real-time data feed for SSE streaming.

    Args:
        session: Database session
        task_id: The task this log belongs to
        agent_output: The AgentOutput from an agent
        step_number: The step in the workflow (0 for planning)
    """
    from backend.app.db.models import AgentLog

    log_entry = AgentLog(
        task_id=task_id,
        agent_persona=agent_output.agent_persona.value,
        step_number=step_number,
        ui_title=agent_output.ui_title,
        ui_subtitle=agent_output.ui_subtitle,
        technical_reasoning=agent_output.technical_reasoning,
        tool_calls=[tc.model_dump(mode='json') for tc in agent_output.tool_calls],
        confidence_score=agent_output.confidence_score,
        requires_review=agent_output.requires_review,
    )
    session.add(log_entry)

    logger.info(
        "agent_output_logged",
        task_id=str(task_id),
        agent=agent_output.agent_persona.value,
        step=step_number,
        confidence=agent_output.confidence_score,
    )


async def log_system_error(
    session: AsyncSession,
    task_id: UUID,
    error: Exception,
    error_context: str = "",
) -> None:
    """
    Log a system error as an AgentLog entry.

    This ensures even crashes are visible in the SSE stream.

    Args:
        session: Database session
        task_id: The task that crashed
        error: The exception that occurred
        error_context: Additional context about where the error occurred
    """
    from backend.app.db.models import AgentLog

    error_log = AgentLog(
        task_id=task_id,
        agent_persona="system",
        step_number=-1,  # Negative to indicate system error
        ui_title="❌ System Error",
        ui_subtitle="An unexpected error occurred during task execution.",
        technical_reasoning=json.dumps({
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_context": error_context,
            "traceback": traceback.format_exc(),
        }, indent=2),
        tool_calls=[],
        confidence_score=0.0,
        requires_review=True,
    )
    session.add(error_log)

    logger.error(
        "system_error_logged",
        task_id=str(task_id),
        error_type=type(error).__name__,
        error_message=str(error),
    )


async def _get_task(session: AsyncSession, task_id: str):
    """Get task from database by ID."""
    from backend.app.db.models import Task

    result = await session.execute(
        select(Task).where(Task.id == UUID(task_id))
    )
    return result.scalar_one_or_none()


async def _get_repository(session: AsyncSession, repo_id: UUID):
    """Get repository from database by ID."""
    from backend.app.db.models import Repository

    result = await session.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    return result.scalar_one_or_none()


# =============================================================================
# Phase 1: Planning Pipeline
# =============================================================================


async def _run_planning_phase(
    session: AsyncSession,
    task,
    repo,
    context: dict,
) -> tuple[bool, str | None]:
    """
    Execute the planning phase of the workflow.

    Returns:
        Tuple of (success, error_message)
    """
    from gravity_core.agents.planner import PlannerAgent
    from gravity_core.llm import LLMClient
    from gravity_core.memory.project_map import ProjectMap

    from backend.app.db.models import TaskStatus

    # --- Step 1: Initialize Services ---
    llm_client = LLMClient(
        openai_api_key=settings.openai_api_key,
        gemini_api_key=settings.google_api_key,
        enable_fallback=True,
        max_retries=3,
    )

    # Build project context via RAG
    project_map = ProjectMap(repo.path)
    await project_map.scan()

    # --- Step 2: Update Task Status to PLANNING ---
    task.status = TaskStatus.PLANNING
    task.current_agent = "planner"
    await session.commit()

    logger.info(
        "planning_phase_started",
        task_id=str(task.id),
        repo_path=repo.path,
    )

    # --- Step 3: Dispatch Planner Agent ---
    planner = PlannerAgent(
        llm_client=llm_client,
        project_map=project_map,
        model_name=settings.default_llm_model or "gpt-4o",
    )

    # Add project context to the execution context
    context["project_context"] = project_map.to_context()

    plan_output = await planner.execute(task.id, context)

    # --- Step 4: Log the Planning Output ---
    await log_agent_output(
        session=session,
        task_id=task.id,
        agent_output=plan_output,
        step_number=0,
    )

    # --- Step 5: Store the Plan ---
    try:
        # Parse the TaskPlan from technical_reasoning
        reasoning = json.loads(plan_output.technical_reasoning)
        task.task_plan = reasoning.get("task_plan", {})
    except (json.JSONDecodeError, KeyError):
        task.task_plan = {"summary": plan_output.ui_subtitle, "steps": []}

    # --- Step 6: State Transition Based on Confidence ---
    if plan_output.requires_review or plan_output.confidence_score < 0.7:
        # Low confidence → requires human review
        task.status = TaskStatus.PLAN_REVIEW
        await session.commit()

        logger.info(
            "task_awaiting_plan_review",
            task_id=str(task.id),
            confidence=plan_output.confidence_score,
        )
        return True, None  # Success, but paused for review
    else:
        # High confidence → proceed to execution
        task.status = TaskStatus.EXECUTING
        await session.commit()

        # ---------------------------------------------------------------------
        # GRAPH EXECUTOR: Materialize Plan to Database (Recursion + DAG)
        # ---------------------------------------------------------------------
        # Convert the JSON plan into real Task/Dependency rows
        await _materialize_plan_to_db(session, task)

        logger.info(
            "planning_phase_complete",
            task_id=str(task.id),
            steps=len(task.task_plan.get("steps", [])),
        )
        return True, None


async def _materialize_plan_to_db(
    session: AsyncSession,
    root_task,
) -> None:
    """
    Convert the flat JSON Plan into a Recursive DAG in the database.

    1. Creates child Task for each step.
    2. Creates TaskDependency rows for edges.
    """
    from backend.app.db.models import Task, TaskDependency, TaskStatus

    plan = root_task.task_plan
    steps = plan.get("steps", [])

    # Map step_id (string) -> db_task_id (UUID)
    id_map: dict[str, UUID] = {}

    # Pass 1: Create all Task Nodes
    for step in steps:
        step_id = step.get("step_id")
        # Fallback for legacy numerical order if step_id missing
        if not step_id:
            step_id = f"step_{step.get('order')}"

        child_task = Task(
            repo_id=root_task.repo_id,
            parent_task_id=root_task.id,
            user_request=step.get("description"),
            title=step_id,
            status=TaskStatus.PENDING,
            # We store the specific agent required in the task metadata if needed,
            # currently we just rely on the description context or explicit assignment later.
            # But here we can inject the persona into the context for the runner.
        )
        session.add(child_task)
        await session.flush() # flush to get UUID
        id_map[step_id] = child_task.id

        # Store metadata in blackboard? Or just task_plan?
        # For now, simpler is better: The Child Task's "user_request" IS the instruction.

    # Pass 2: Create Edges (Dependencies)
    for step in steps:
        step_id = step.get("step_id") or f"step_{step.get('order')}"
        blocker_ids = step.get("depends_on", [])

        # Fallback for integer dependencies
        legacy_deps = step.get("dependencies", [])
        if legacy_deps:
            # Map integers back to steps? This assumes order.
            # Safety fallback: logical order 1 -> 2 -> 3
            pass

        child_uuid = id_map[step_id]

        for blocker_key in blocker_ids:
            if blocker_key in id_map:
                blocker_uuid = id_map[blocker_key]
                dependency = TaskDependency(
                    blocker_task_id=blocker_uuid,
                    blocked_task_id=child_uuid,
                    reason="Planned Dependency"
                )
                session.add(dependency)
            else:
                logger.warning("missing_dependency_ref", step=step_id, missing=blocker_key)

    await session.commit()


# =============================================================================
# Phase 2: Execution Pipeline (Code → Test → Fix Loop)
# =============================================================================


# =============================================================================
# Phase 2: Execution Pipeline (Topological DAG Executor)
# =============================================================================


async def _execute_dag_workflow(
    session: AsyncSession,
    root_task,
    repo,
    context: dict,
    max_fix_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Execute the workflow using a Topological Scheduler (Dynamic Nervous System).

    Status: LIVE (Phase IV.5)

    Pipeline:
    1. POLL: Scheduler.get_next_executable_tasks()
    2. EXECUTE: Dispatch Agent for the task
    3. VALIDATE: Referee.validate_contract()
    4. LOOP: Repeat until all tasks complete or failure.
    """
    from backend.app.services.scheduler import SchedulerService
    from gravity_core.guardrails.referee import Referee
    from backend.app.db.models import Task, TaskStatus

    scheduler = SchedulerService(session)
    referee = Referee(repo.path)

    logger.info("dag_workflow_started", root_task_id=str(root_task.id))

    # Safety: Emergency Stop Timeout
    start_time = datetime.now(timezone.utc)
    TIMEOUT_SECONDS = 600 # 10 minutes max for now

    while True:
        # Check Timeout
        if (datetime.now(timezone.utc) - start_time).total_seconds() > TIMEOUT_SECONDS:
             return False, "Emergency Stop: Workflow timed out."

        # -----------------------------------------------------------------
        # SIGNAL CHECK (Protocol: Deterministic Reality)
        # -----------------------------------------------------------------
        # Retrieve freshest state
        await session.refresh(root_task)

        # PAUSE LOOP: Sleep indefinitely while paused
        while root_task.status == TaskStatus.PAUSED:
             logger.info("workflow_paused", root_task_id=str(root_task.id))
             await asyncio.sleep(5) # Slow heartbeat when paused
             await session.refresh(root_task) # Check again

        # KILL SWITCH: Stop if archived or deleted
        if root_task.status in [TaskStatus.ARCHIVED, TaskStatus.FAILED] or root_task.status == "DELETED":
             logger.info("workflow_terminated", root_task_id=str(root_task.id), status=root_task.status)
             return False, "Task was terminated by user."

        # 1. POLL: Get Ready Tasks
        executable_tasks = await scheduler.get_next_executable_tasks(root_task.id)

        if not executable_tasks:
            # No tasks ready. Are we done?
            stmt = select(func.count()).where(
                Task.parent_task_id == root_task.id,
                Task.status != TaskStatus.COMPLETED
            )
            count = (await session.execute(stmt)).scalar()

            if count == 0:
                logger.info("dag_workflow_victory", root_task_id=str(root_task.id))
                break # VICTORY
            else:
                # Tasks remaining but none ready.
                # Could be waiting for Async events, or Deadlock.
                # For now, we WAIT.
                logger.debug("dag_workflow_waiting", root_task_id=str(root_task.id), remaining=count)
                await asyncio.sleep(2) # Pulse Check
                continue

        # 2. SELECT: Pick priority task
        current_task = executable_tasks[0]

        logger.info(
            "scheduler_selected_task",
            task_id=str(current_task.id),
            title=current_task.title
        )

        # 3. EXECUTE: Run the task
        success, error = await _execute_single_task(
            session=session,
            task=current_task,
            root_context=context,
            max_fix_attempts=max_fix_attempts
        )

        # 4. REVIEW CHECK (Pause if needed)
        if current_task.status in [TaskStatus.REVIEW_REQUIRED, TaskStatus.PLAN_REVIEW]:
             logger.info("workflow_paused_for_review", subtask=str(current_task.id))
             return True, None

        # 5. VALIDATE & FEEDBACK LOOP
        # Even if Agent thinks it succeeded, Referee checks contracts.
        if success:
             is_valid, validation_msg = referee.validate_contract(current_task.definition_of_done)

             if is_valid:
                 # SUCCESS CONFIRMED
                 current_task.status = TaskStatus.COMPLETED
                 current_task.completed_at = datetime.now(timezone.utc)
                 await session.commit()
                 logger.info("referee_accepted", task=current_task.title)

             else:
                 # FEEDBACK LOOP: REJECT & RETRY
                 logger.warning("referee_rejected", task=current_task.title, reason=validation_msg)

                 # Check Retry Limit
                 if current_task.retry_count >= 3:
                     current_task.status = TaskStatus.FAILED
                     current_task.error_message = f"Referee rejection limit reached. Last error: {validation_msg}"
                     await session.commit()
                     return False, f"Task '{current_task.title}' failed Referee check 3 times."

                 # Inject Logic Back into Task
                 current_task.status = TaskStatus.PENDING # Reset to Pending so Scheduler picks it up
                 current_task.retry_count += 1

                 # Append Feedback to user_request so Agent sees it next time
                 feedback = f"\n\n[SYSTEM FEEDBACK]: Previous attempt rejected. Reason: {validation_msg}"
                 if feedback not in current_task.user_request:
                     current_task.user_request += feedback

                 await session.commit()
                 logger.info("task_reset_for_retry", task=current_task.title, attempt=current_task.retry_count)
                 continue # Loop back immediately

        elif not success:
             # Logic execution failed (e.g. tests failed hard)
             return False, f"Task '{current_task.title}' Logic Failed: {error}"

    # =================================================================
    # Final Documentation Phase (Run once after DAG completes)
    # =================================================================

    root_task.status = TaskStatus.DOCUMENTING
    root_task.current_agent = "docs"
    await session.commit()

    # Dispatch DocsAgent
    # We need to collect changes from subtasks if we want to document them.
    # For now, simple pass.
    success, error = await _run_documentation_phase(
        session=session,
        task=root_task,
        repo=repo,
        context=context,
        all_changes={}, # TODO: Aggregate changes from subtasks
    )

    if not success:
        logger.warning(
            "documentation_phase_failed",
            task_id=str(root_task.id),
            error=error,
        )

    # Mark root task as completed
    root_task.status = TaskStatus.COMPLETED
    root_task.current_agent = None
    root_task.completed_at = datetime.now(timezone.utc)
    await session.commit()

    logger.info(
        "execution_phase_complete",
        task_id=str(root_task.id),
        loops=loop_count,
    )

    return True, None


async def _execute_single_task(
    session: AsyncSession,
    task,
    root_context: dict,
    max_fix_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Execute a single atomic task (Code -> Test -> Fix).
    Extracted from the old linear loop.
    """
    from gravity_core.agents.coder import CoderAgent
    from gravity_core.agents.qa import QAAgent
    from gravity_core.llm import LLMClient
    from backend.app.db.models import TaskStatus

    # Initialize shared LLM client
    llm_client = LLMClient(
        openai_api_key=settings.openai_api_key,
        gemini_api_key=settings.google_api_key, # Corrected config access
        enable_fallback=True,
        max_retries=3,
    )

    test_commands = root_context.get("test_commands", ["pytest"])
    last_changeset = {}

    # task.current_step is less relevant now, but we can keep it for UI
    task.status = TaskStatus.EXECUTING

    # Determine persona from title or metadata?
    # Schema doesn't have explicit persona column on Task yet, relying on planner to put it in description/title?
    # Or we default to coder_be.
    # Ideally, Task model has 'assigned_agent' column.
    # For now, let's look at the TaskPlan step dict if we can find it?
    # The 'task' object here is a DB Task.

    # Hack for Phase IV: Default to Coder BE unless "docs" or "qa" in title
    agent_persona = "coder_be"
    specialty = "be"

    task.current_agent = agent_persona
    await session.commit()

    step_context = {
        **root_context,
        "task_description": task.user_request,
        # "step": step, # We don't have the dictionary step here easily unless we parse root plan
    }

    # =============================================================
    # Code → Test → Fix Loop
    # =============================================================


    # =============================================================
    # Code → Test → Fix Loop
    # =============================================================

    # NEW: Determine if we have sub-steps from the plan
    # If the task has a structured plan (from PlannerAgent), we should try to follow it.
    # However, currently `task.task_plan` is a JSON blob for the whole mission.
    # The `current_task` is usually a leaf node in the DAG.
    # Let's assume the Agent (LLM) is smart enough to see the request and execute it.
    # But to enforce "Ghost Code" fix, we will check the OUTPUT of the agent.

    fix_attempts = 0
    from pathlib import Path

    while fix_attempts < max_fix_attempts:
        # --- CODER: Write/fix code ---
        coder = CoderAgent(
            specialty=specialty,
            llm_client=llm_client,
            model_name=settings.default_llm_model,
        )

        coder_output = await coder.execute(task.id, step_context)

        # Log coder output
        await log_agent_output(
             session=session,
             task_id=task.id,
             agent_output=coder_output,
             step_number=0,
        )

        # -------------------------------------------------------------
        # PROTOCOL DETERMINISTIC REALITY: The Verify Stage
        # -------------------------------------------------------------
        # Scan the agent's output for file operations and physically check disk.

        reality_check_passed = True
        missing_files = []

        # We inspect the specialized `_changes` list from the CoderAgent if accessible,
        # or we parse the `tool_calls` from the output.
        # CoderAgent returns an AgentOutput which has `tool_calls`.

        if coder_output.tool_calls:
            for tool in coder_output.tool_calls:
                if tool.tool_name in ["create_new_module", "edit_file_snippet", "write_to_file"]:
                    # Extract target path
                    target_path = tool.arguments.get("file_path") or tool.arguments.get("path") or tool.arguments.get("target_file")

                    if target_path:
                        # Normalize path
                        real_path = Path(target_path)
                        if not real_path.is_absolute():
                             # Dangerous assumption, but Coder usually tries absolute.
                             # If relative, treat as relative to repo root (not implemented here safely yet)
                             pass

                        if not real_path.exists():
                             logger.warning("reality_check_failed", task_id=str(task.id), missing_file=str(real_path))
                             missing_files.append(str(real_path))
                             reality_check_passed = False
                        else:
                             logger.info("reality_check_passed", file=str(real_path))

        if not reality_check_passed:
             error_msg = f"Reality Check Failed: Agent claimed to create files, but they are missing from disk: {', '.join(missing_files)}"

             # If we haven't maxed out retries, loop back immediately with this error
             fix_attempts += 1

             # Update context to SCREAM at the agent
             step_context["system_feedback"] = f"CRITICAL ERROR: You claimed to create file(s) {missing_files}, but I checked the OS and they are MISSING. You likely hallucinated the tool call or the path is wrong. TRY AGAIN. USE THE TOOLS."

             logger.warning("forcing_retry_ghost_code", task_id=str(task.id), attempt=fix_attempts)
             continue

        # If Coder succeeds and verifies, we proceed to QA (if applicable)
        # For pure "Setup" tasks, Coder success might be enough.
        # But we still run the standard loop.

        # Track changeset
        try:
            reasoning = json.loads(coder_output.technical_reasoning)
            changes = reasoning.get("changes", [])
            if changes:
                last_changeset = changes[0]
        except (json.JSONDecodeError, KeyError):
            pass

        # Check review
        if coder_output.requires_review:
            task.status = TaskStatus.REVIEW_REQUIRED
            await session.commit()
            return True, None # Pause

        await session.commit()

        # --- QA: Run tests ---
        task.current_agent = "qa"
        task.status = TaskStatus.TESTING
        await session.commit()

        qa = QAAgent(
            llm_client=llm_client,
            model_name=settings.default_llm_model,
            max_fix_attempts=max_fix_attempts,
        )

        qa_context = {
            **root_context,
            "test_commands": test_commands,
            "last_changeset": last_changeset,
            "task_goal": task.user_request,
        }

        qa_output = await qa.execute(task.id, qa_context)

        await log_agent_output(
            session=session,
            task_id=task.id,
            agent_output=qa_output,
            step_number=0,
        )

        # Check test results
        if qa_output.confidence_score >= 0.9:
            # Passed
            break

        # Failed
        if qa.has_suggested_fix():
            fix_attempts += 1
            suggested_fix = qa.get_suggested_fix()

            logger.info("applying_suggested_fix", task_id=str(task.id), attempt=fix_attempts)

            step_context["suggested_fix"] = {
                "tool_call": suggested_fix.model_dump() if suggested_fix else None,
                "attempt": fix_attempts
            }
            continue
        else:
            # Failed no fix
            if qa_output.confidence_score < 0.5:
                # task.status = TaskStatus.FAILED # Caller handles status
                return False, "Tests failed without automatic fix"
            break

    # Max attempts
    if fix_attempts >= max_fix_attempts:
        logger.warning("max_fix_attempts_reached", task_id=str(task.id))

    return True, None


# =============================================================================
# Phase 3: Documentation Pipeline
# =============================================================================


async def _run_documentation_phase(
    session: AsyncSession,
    task,
    repo,
    context: dict,
    all_changes: dict,
) -> tuple[bool, str | None]:
    """
    Execute the documentation phase - final step before completion.

    Args:
        session: Database session
        task: The task being executed
        repo: Repository model
        context: Execution context
        all_changes: Accumulated ChangeSets from Coder

    Returns:
        Tuple of (success, error_message)
    """
    from gravity_core.agents.docs import DocsAgent
    from gravity_core.llm import LLMClient

    logger.info(
        "documentation_phase_started",
        task_id=str(task.id),
    )

    try:
        # Initialize LLM client
        llm_client = LLMClient(
            openai_api_key=settings.openai_api_key,
            gemini_api_key=settings.google_api_key,
            enable_fallback=True,
            max_retries=3,
        )

        # Initialize DocsAgent
        docs = DocsAgent(
            llm_client=llm_client,
            model_name=settings.default_llm_model,
        )

        # Build docs context
        docs_context = {
            **context,
            "changes": [all_changes] if all_changes else [],
            "plan_summary": task.task_plan.get("summary", "") if task.task_plan else "",
        }

        # Execute documentation generation
        docs_output = await docs.execute(task.id, docs_context)

        # Log docs output
        await log_agent_output(
            session=session,
            task_id=task.id,
            agent_output=docs_output,
            step_number=task.current_step or 0,
        )

        logger.info(
            "documentation_phase_complete",
            task_id=str(task.id),
            docs_generated=len(docs.get_doc_changes()),
        )

        return True, None

    except Exception as e:
        logger.error(
            "documentation_phase_error",
            task_id=str(task.id),
            error=str(e),
        )
        return False, str(e)


# =============================================================================
# Main Orchestration Loop
# =============================================================================


async def _run_task_async(task_id: str) -> None:
    """
    Execute the complete agent workflow for a task.

    Pipeline:
    1. INITIALIZATION - Load Task and Repository
    2. PLANNING - PlannerAgent creates TaskPlan
    3. STATE CHECK - Determine if review needed
    4. (Future) EXECUTION - Coder agents execute steps
    5. (Future) TESTING - QA agent runs tests
    6. (Future) DOCUMENTATION - Docs agent updates docs
    """
    from backend.app.db.models import TaskStatus

    logger.info("worker_task_started", task_id=task_id)

    async with worker_session_factory() as session:
        task = None

        try:
            # =================================================================
            # Step 1: INITIALIZATION - Load Task and Repository
            # =================================================================

            task = await _get_task(session, task_id)
            if not task:
                logger.error("task_not_found", task_id=task_id)
                return

            repo = await _get_repository(session, task.repo_id)
            if not repo:
                task.status = TaskStatus.FAILED
                task.error_message = "Repository not found"
                await session.commit()
                logger.error(
                    "repository_not_found",
                    task_id=task_id,
                    repo_id=str(task.repo_id),
                )
                return

            # Build execution context
            context = {
                "user_request": task.user_request,
                "repo_path": repo.path,
            }

            # =================================================================
            # Step 2: PLANNING PHASE
            # =================================================================

            # Skip planning if we are already executed/verified
            if task.status == TaskStatus.EXECUTING and task.task_plan:
                logger.info("skipping_planning_already_verified", task_id=task_id)
            else:
                success, error = await _run_planning_phase(
                    session=session,
                    task=task,
                    repo=repo,
                    context=context,
                )

                if not success:
                    task.status = TaskStatus.FAILED
                    task.error_message = error
                    await session.commit()
                    return

                # If status is PLAN_REVIEW, we stop here and wait for approval
                if task.status == TaskStatus.PLAN_REVIEW:
                    logger.info(
                        "workflow_paused_for_review",
                        task_id=task_id,
                    )
                    return

            # =================================================================
            # Step 3: EXECUTION PHASE (Code → Test → Fix Loop)
            # =================================================================

            # =================================================================
            # Step 3: EXECUTION PHASE (Topological DAG Workflow)
            # =================================================================

            success, error = await _execute_dag_workflow(
                session=session,
                root_task=task,
                repo=repo,
                context=context,
            )

            if not success:
                task.status = TaskStatus.FAILED
                task.error_message = error
                await session.commit()
                return

            logger.info(
                "workflow_complete",
                task_id=task_id,
                status=task.status.value,
            )

        except Exception as e:
            # =================================================================
            # GRACEFUL FAILURE HANDLING
            # =================================================================

            logger.exception(
                "worker_task_error",
                task_id=task_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )

            # Update task status to FAILED
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = f"{type(e).__name__}: {str(e)}"
                task.retry_count += 1
                task.updated_at = datetime.now(timezone.utc)

                # Log the crash to AgentLog for SSE visibility
                try:
                    await log_system_error(
                        session=session,
                        task_id=task.id,
                        error=e,
                        error_context="Worker orchestration failed",
                    )
                except Exception as log_error:
                    logger.error(
                        "failed_to_log_system_error",
                        task_id=task_id,
                        log_error=str(log_error),
                    )

                await session.commit()


# =============================================================================
# Dramatiq Actor Definition
# =============================================================================


@dramatiq.actor(
    max_retries=3,
    time_limit=300_000,  # 5 minute time limit per attempt
    min_backoff=1000,    # 1 second minimum backoff
    max_backoff=60000,   # 60 second maximum backoff
)
def run_task(task_id: str) -> None:
    """
    Dramatiq actor for running tasks.

    This is the entry point called by the task queue.
    It wraps the async execution in an event loop.

    Settings:
        max_retries: 3 attempts before permanent failure
        time_limit: 5 minutes per attempt
        min_backoff: 1 second minimum backoff
        max_backoff: 60 seconds max between retries
    """
    print(f"WORKER_RECEIVED_TASK: {task_id}")
    logger.info("dramatiq_actor_received", task_id=task_id)
    asyncio.run(_run_task_async(task_id))


@dramatiq.actor(max_retries=0, time_limit=60_000)
def resume_task(task_id: str, approved: bool = True) -> None:
    """
    Resume a task after human review.

    Called when a task in PLAN_REVIEW status is approved or rejected.

    Args:
        task_id: The task to resume
        approved: Whether the plan was approved (True) or rejected (False)
    """
    asyncio.run(_resume_task_async(task_id, approved))


async def _create_worker_engine():
    """Create an isolated engine for the current asyncio loop."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


async def _resume_task_async(task_id: str, approved: bool) -> None:
    """Resume a paused task after review."""
    from backend.app.db.models import TaskStatus

    engine = await _create_worker_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            task = await _get_task(session, task_id)
            if not task:
                logger.error("resume_task_not_found", task_id=task_id)
                return

            if approved:
                task.status = TaskStatus.EXECUTING
                logger.info("task_resumed_approved", task_id=task_id)
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "Plan rejected by user"
                logger.info("task_resume_rejected", task_id=task_id)

            await session.commit()
    finally:
        await engine.dispose()


# =============================================================================
# Main Orchestration Loop
# =============================================================================


async def _run_task_async(task_id: str) -> None:
    """
    Execute the complete agent workflow for a task.

    Pipeline:
    1. INITIALIZATION - Load Task and Repository
    2. PLANNING - PlannerAgent creates TaskPlan
    3. STATE CHECK - Determine if review needed
    4. (Future) EXECUTION - Coder agents execute steps
    5. (Future) TESTING - QA agent runs tests
    6. (Future) DOCUMENTATION - Docs agent updates docs
    """
    from backend.app.db.models import TaskStatus

    logger.info("worker_task_started", task_id=task_id)

    # Create engine local to this loop
    engine = await _create_worker_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            task = None

            try:
                # =================================================================
                # Step 1: INITIALIZATION - Load Task and Repository
                # =================================================================

                task = await _get_task(session, task_id)
                if not task:
                    logger.error("task_not_found", task_id=task_id)
                    return

                repo = await _get_repository(session, task.repo_id)
                if not repo:
                    task.status = TaskStatus.FAILED
                    task.error_message = "Repository not found"
                    await session.commit()
                    logger.error(
                        "repository_not_found",
                        task_id=task_id,
                        repo_id=str(task.repo_id),
                    )
                    return

                # Build execution context
                context = {
                    "user_request": task.user_request,
                    "repo_path": repo.path,
                }

                # =================================================================
                # Step 2: PLANNING PHASE
                # =================================================================

                # Skip planning if we are already executed/verified
                if task.status == TaskStatus.EXECUTING and task.task_plan:
                    logger.info("skipping_planning_already_verified", task_id=task_id)
                else:
                    success, error = await _run_planning_phase(
                        session=session,
                        task=task,
                        repo=repo,
                        context=context,
                    )

                    if not success:
                        task.status = TaskStatus.FAILED
                        task.error_message = error
                        await session.commit()
                        return

                # If status is PLAN_REVIEW, we stop here and wait for approval
                if task.status == TaskStatus.PLAN_REVIEW:
                    logger.info(
                        "workflow_paused_for_review",
                        task_id=task_id,
                    )
                    return

                # =================================================================
                # Step 3: EXECUTION PHASE (Code → Test → Fix Loop)
                # =================================================================

                success, error = await _execute_dag_workflow(
                    session=session,
                    root_task=task,
                    repo=repo,
                    context=context,
                )

                if not success:
                    task.status = TaskStatus.FAILED
                    task.error_message = error
                    await session.commit()
                    return

                logger.info(
                    "workflow_complete",
                    task_id=task_id,
                    status=task.status.value,
                )

            except Exception as e:
                # =================================================================
                # GRACEFUL FAILURE HANDLING
                # =================================================================

                logger.exception(
                    "worker_task_error",
                    task_id=task_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

                # Update task status to FAILED
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"{type(e).__name__}: {str(e)}"
                    task.retry_count += 1
                    task.updated_at = datetime.now(timezone.utc)

                    # Log the crash to AgentLog for SSE visibility
                    try:
                        await log_system_error(
                            session=session,
                            task_id=task.id,
                            error=e,
                            error_context="Worker orchestration failed",
                        )
                    except Exception as log_error:
                        logger.error(
                            "failed_to_log_system_error",
                            task_id=task_id,
                            log_error=str(log_error),
                        )

                    await session.commit()
    finally:
        await engine.dispose()

@asynccontextmanager
async def worker_session_factory():
    """
    Context manager for worker database sessions.
    Creates a new engine and session for each task execution to ensure isolation.
    """
    engine = await _create_worker_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

    await engine.dispose()
