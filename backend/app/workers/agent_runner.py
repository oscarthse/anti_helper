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

import asyncio
import json
import traceback
from datetime import UTC, datetime
from uuid import UUID

import dramatiq
import structlog
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Broker and Session Configuration
# =============================================================================

# Configure Redis broker for Dramatiq
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)

# Create async engine specifically for worker processes
# (separate from the main API engine to avoid connection pool conflicts)
worker_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
worker_session_factory = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


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

        logger.info(
            "planning_phase_complete",
            task_id=str(task.id),
            steps=len(task.task_plan.get("steps", [])),
        )
        return True, None


# =============================================================================
# Phase 2: Execution Pipeline (Code → Test → Fix Loop)
# =============================================================================


async def _run_execution_phase(
    session: AsyncSession,
    task,
    repo,
    context: dict,
    max_fix_attempts: int = 3,
) -> tuple[bool, str | None]:
    """
    Execute the coding and testing phase with automated fix loop.

    Pipeline for each step:
    1. CoderAgent writes code
    2. QAAgent runs tests
    3. If tests fail with fix suggestion → re-dispatch Coder → loop
    4. After max_fix_attempts or success → next step

    Returns:
        Tuple of (success, error_message)
    """
    from gravity_core.agents.coder import CoderAgent
    from gravity_core.agents.qa import QAAgent
    from gravity_core.llm import LLMClient

    from backend.app.db.models import TaskStatus

    # Initialize shared LLM client
    llm_client = LLMClient(
        openai_api_key=settings.openai_api_key,
        gemini_api_key=settings.google_api_key,
        enable_fallback=True,
        max_retries=3,
    )

    steps = task.task_plan.get("steps", []) if task.task_plan else []
    test_commands = context.get("test_commands", ["pytest"])
    last_changeset = {}

    logger.info(
        "execution_phase_started",
        task_id=str(task.id),
        step_count=len(steps),
    )

    # =================================================================
    # Execute each step from the TaskPlan
    # =================================================================

    for step_index, step in enumerate(steps):
        task.current_step = step_index + 1
        task.status = TaskStatus.EXECUTING

        agent_persona = step.get("agent_persona", "coder_be")

        # Skip non-coder steps for now
        if not agent_persona.startswith("coder"):
            continue

        specialty = agent_persona.replace("coder_", "")
        task.current_agent = agent_persona
        await session.commit()

        # Build step context
        step_context = {
            **context,
            "step": step,
            "plan": task.task_plan,
        }

        # =============================================================
        # Code → Test → Fix Loop
        # =============================================================

        fix_attempts = 0

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
                step_number=step_index + 1,
            )

            # Track last changeset for QA diagnosis
            try:
                reasoning = json.loads(coder_output.technical_reasoning)
                changes = reasoning.get("changes", [])
                if changes:
                    last_changeset = changes[0]
            except (json.JSONDecodeError, KeyError):
                pass

            # Check if coder needs review
            if coder_output.requires_review:
                task.status = TaskStatus.REVIEW_REQUIRED
                await session.commit()
                logger.info(
                    "step_awaiting_review",
                    task_id=str(task.id),
                    step=step_index + 1,
                )
                return True, None  # Pause for human review

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
                **context,
                "test_commands": test_commands,
                "last_changeset": last_changeset,
                "plan_step": step,
            }

            qa_output = await qa.execute(task.id, qa_context)

            # Log QA output
            await log_agent_output(
                session=session,
                task_id=task.id,
                agent_output=qa_output,
                step_number=step_index + 1,
            )

            # Check test results
            if qa_output.confidence_score >= 0.9:
                # Tests passed! Move to next step
                logger.info(
                    "step_tests_passed",
                    task_id=str(task.id),
                    step=step_index + 1,
                )
                break

            # Tests failed - check for fix suggestion
            if qa.has_suggested_fix():
                fix_attempts += 1
                suggested_fix = qa.get_suggested_fix()

                logger.info(
                    "applying_suggested_fix",
                    task_id=str(task.id),
                    step=step_index + 1,
                    attempt=fix_attempts,
                    fix_file=suggested_fix.arguments.get("file_path") if suggested_fix else None,
                )

                # Add fix to context for next coder iteration
                step_context["suggested_fix"] = {
                    "tool_call": suggested_fix.model_dump() if suggested_fix else None,
                    "attempt": fix_attempts,
                }

                # Loop back to coder with fix instruction
                continue

            else:
                # No fix suggested - tests failed, needs human review
                logger.warning(
                    "step_tests_failed_no_fix",
                    task_id=str(task.id),
                    step=step_index + 1,
                )

                if qa_output.confidence_score < 0.5:
                    task.status = TaskStatus.FAILED
                    task.error_message = "Tests failed and no automatic fix available"
                    await session.commit()
                    return False, "Tests failed without automatic fix"

                break  # Move on despite failure

        # Max fix attempts reached
        if fix_attempts >= max_fix_attempts:
            logger.warning(
                "max_fix_attempts_reached",
                task_id=str(task.id),
                step=step_index + 1,
                attempts=fix_attempts,
            )

    # =================================================================
    # All steps complete → move to DOCUMENTING
    # =================================================================

    task.status = TaskStatus.DOCUMENTING
    task.current_agent = "docs"
    await session.commit()

    # Dispatch DocsAgent
    success, error = await _run_documentation_phase(
        session=session,
        task=task,
        repo=repo,
        context=context,
        all_changes=last_changeset,  # Pass accumulated changes
    )

    if not success:
        logger.warning(
            "documentation_phase_failed",
            task_id=str(task.id),
            error=error,
        )
        # Documentation failure is non-fatal - continue to completion

    # Mark as completed
    task.status = TaskStatus.COMPLETED
    task.current_agent = None
    task.completed_at = datetime.now(UTC)
    await session.commit()

    logger.info(
        "execution_phase_complete",
        task_id=str(task.id),
        steps_executed=len(steps),
    )

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

            success, error = await _run_execution_phase(
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
                task.updated_at = datetime.now(UTC)

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
        min_backoff: 1 second between retries
        max_backoff: 60 seconds max between retries
    """
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


async def _resume_task_async(task_id: str, approved: bool) -> None:
    """Resume a paused task after review."""
    from backend.app.db.models import TaskStatus

    async with worker_session_factory() as session:
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
