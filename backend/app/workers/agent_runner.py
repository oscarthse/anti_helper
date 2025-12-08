"""
Agent Runner Worker - Dramatiq Task Execution

This worker orchestrates the agent workflow pipeline.
It picks up tasks from the queue and executes:
    Task Creation → Planning → State Update → DAG Execution

Key Responsibilities:
1. Load Task and Repository from database
2. Initialize LLMClient and ProjectMap (RAG context)
3. Dispatch PlannerAgent to create TaskPlan
4. Log all agent outputs to AgentLog table (SSE streaming source)
5. Transition task state based on confidence score
6. Use DAGExecutor for clean workflow execution
7. Handle errors gracefully with proper logging

Architecture:
    run_task (Dramatiq Actor)
        └── _run_task_async
             ├── _run_planning_phase  → PlannerAgent
             ├── _materialize_plan_to_db  → Create subtask DAG
             └── DAGExecutor.execute  → Clean workflow execution
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure libs directory is in python path for gravity_core imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
libs_path = project_root / "libs"
if str(libs_path) not in sys.path:
    sys.path.append(str(libs_path))

import asyncio
import json
import traceback
from datetime import datetime, timezone
from uuid import UUID

import dramatiq
import structlog
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Broker Configuration
# =============================================================================

redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)


# =============================================================================
# Database Engine Factory
# =============================================================================


async def _create_worker_engine():
    """Create an isolated engine for the current asyncio loop."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


# =============================================================================
# Utility Functions (Exported for use by other modules)
# =============================================================================


async def log_agent_output(
    session: AsyncSession,
    task_id: UUID,
    agent_output,
    step_number: int = 0,
    root_task_id: UUID | None = None,
) -> None:
    """
    Insert an AgentOutput into the AgentLog table and publish to Redis.

    This is the explainability trigger - every agent action is logged
    with both technical details and user-facing explanations.

    CRITICAL: After DB insert, we publish to Redis for SSE streaming.
    This enables real-time updates without database polling.

    Args:
        session: Database session
        task_id: The task this log belongs to
        agent_output: The AgentOutput from an agent
        step_number: The step in the workflow (0 for planning)
        root_task_id: If provided, also publish to root task channel for subtask logs
    """
    from backend.app.db.models import AgentLog
    from backend.app.core.events import get_event_bus

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
    await session.flush()  # Flush to get the ID

    # -------------------------------------------------------------------------
    # REDIS PUB/SUB: Publish event for SSE streaming
    # This fires immediately after DB write, enabling real-time updates
    # without the SSE endpoint needing to poll the database.
    # -------------------------------------------------------------------------
    log_data = {
        "id": str(log_entry.id),
        "task_id": str(task_id),
        "agent_persona": agent_output.agent_persona.value,
        "step_number": step_number,
        "ui_title": agent_output.ui_title,
        "ui_subtitle": agent_output.ui_subtitle,
        "confidence_score": agent_output.confidence_score,
        "requires_review": agent_output.requires_review,
        "created_at": log_entry.created_at.isoformat() if log_entry.created_at else None,
    }

    try:
        event_bus = get_event_bus()
        # Publish to the subtask's channel
        await event_bus.publish_task_event(
            task_id=str(task_id),
            event_type="agent_log",
            data=log_data,
        )

        # CRITICAL: Also publish to root task channel if this is a subtask
        # This enables frontend (subscribed to root task) to see subtask logs
        if root_task_id and root_task_id != task_id:
            await event_bus.publish_task_event(
                task_id=str(root_task_id),
                event_type="agent_log",
                data=log_data,
            )
    except Exception as e:
        # Fire-and-forget: Don't fail the main operation if Redis is down
        logger.warning("redis_publish_failed", task_id=str(task_id), error=str(e))

    logger.info(
        "agent_output_logged",
        task_id=str(task_id),
        agent=agent_output.agent_persona.value,
        step=step_number,
        confidence=agent_output.confidence_score,
    )


async def publish_verified_file_event(
    task_id: UUID,
    verified_action,  # VerifiedFileAction
    root_task_id: UUID | None = None,
) -> None:
    """
    Publish a verified file action to Redis for SSE streaming.

    CRITICAL: This function ONLY accepts VerifiedFileAction objects,
    which have ALREADY passed disk existence and quality validation.
    This guarantees the UI never receives phantom file events.

    Args:
        task_id: The task that created the file
        verified_action: A VerifiedFileAction (already validated by Pydantic)
        root_task_id: If provided, also publish to root task channel
    """
    from datetime import datetime
    from backend.app.core.events import get_event_bus

    # Use Pydantic model_dump for guaranteed schema compliance
    event_data = {
        "event_type": "file_verified",
        "task_id": str(task_id),
        "step_index": verified_action.step_index,
        "file_path": verified_action.path,
        "file_action": verified_action.action.value,
        "byte_size": verified_action.byte_size,
        "quality_checks": verified_action.quality_checks_passed,
        "quality_warnings": verified_action.quality_warnings,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        event_bus = get_event_bus()

        # Publish to subtask channel
        await event_bus.publish_task_event(
            task_id=str(task_id),
            event_type="file_verified",
            data=event_data,
        )

        # Also publish to root task channel for UI visibility
        if root_task_id and root_task_id != task_id:
            await event_bus.publish_task_event(
                task_id=str(root_task_id),
                event_type="file_verified",
                data=event_data,
            )

        logger.info(
            "verified_file_event_published",
            task_id=str(task_id),
            file_path=verified_action.path,
            step_index=verified_action.step_index,
        )

    except Exception as e:
        # Don't fail the operation if Redis is down
        logger.warning(
            "verified_file_event_publish_failed",
            task_id=str(task_id),
            file_path=verified_action.path,
            error=str(e),
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


# =============================================================================
# Database Helpers
# =============================================================================


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
        reasoning = json.loads(plan_output.technical_reasoning)
        task.task_plan = reasoning.get("task_plan", {})
    except (json.JSONDecodeError, KeyError):
        task.task_plan = {"summary": plan_output.ui_subtitle, "steps": []}

    # --- Step 6: State Transition Based on Confidence ---
    if plan_output.requires_review or plan_output.confidence_score < 0.7:
        task.status = TaskStatus.PLAN_REVIEW
        await session.commit()

        logger.info(
            "task_awaiting_plan_review",
            task_id=str(task.id),
            confidence=plan_output.confidence_score,
        )
        return True, None  # Success, but paused for review
    else:
        task.status = TaskStatus.EXECUTING
        await session.commit()

        # Materialize plan to database (create subtask DAG)
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
        if not step_id:
            step_id = f"step_{step.get('order')}"

        child_task = Task(
            repo_id=root_task.repo_id,
            parent_task_id=root_task.id,
            user_request=step.get("description"),
            title=step_id,
            status=TaskStatus.PENDING,
            # Store step metadata so CoderAgent knows which files to create
            task_plan={
                "files_affected": step.get("files_affected", []),
                "order": step.get("order", 1),
                "step_id": step_id,
                "description": step.get("description"),
            },
        )
        session.add(child_task)
        await session.flush()  # Flush to get UUID
        id_map[step_id] = child_task.id

    # Pass 2: Create Edges (Dependencies)
    for step in steps:
        step_id = step.get("step_id") or f"step_{step.get('order')}"
        blocker_ids = step.get("depends_on", [])

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
                logger.warning(
                    "missing_dependency_ref",
                    step=step_id,
                    missing=blocker_key
                )

    await session.commit()


# =============================================================================
# Main Orchestration
# =============================================================================


async def _run_task_async(task_id: str) -> None:
    """
    Execute the complete agent workflow for a task.

    Pipeline:
    1. INITIALIZATION - Load Task and Repository
    2. PLANNING - PlannerAgent creates TaskPlan
    3. STATE CHECK - Determine if review needed
    4. EXECUTION - DAGExecutor runs the workflow
    """
    from backend.app.db.models import TaskStatus
    from backend.app.services.dag_executor import DAGExecutor

    logger.info("worker_task_started", task_id=task_id)

    # Create engine with proper cleanup
    engine = None
    try:
        engine = await _create_worker_engine()
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        async with session_factory() as session:
            task = None

            try:
                # =============================================================
                # Step 1: INITIALIZATION - Load Task and Repository
                # =============================================================

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

                # =============================================================
                # Step 2: PLANNING PHASE
                # =============================================================

                # Skip planning if already executed/verified
                if task.status == TaskStatus.EXECUTING and task.task_plan:
                    logger.info(
                        "skipping_planning_already_verified",
                        task_id=task_id
                    )
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

                    # If status is PLAN_REVIEW, stop and wait for approval
                    if task.status == TaskStatus.PLAN_REVIEW:
                        logger.info(
                            "workflow_paused_for_review",
                            task_id=task_id,
                        )
                        return

                # =============================================================
                # Step 3: EXECUTION PHASE (DAG Executor)
                # =============================================================

                executor = DAGExecutor(
                    session=session,
                    root_task=task,
                    repo=repo,
                    context=context,
                )

                result = await executor.execute()

                if not result.success:
                    task.status = TaskStatus.FAILED
                    task.error_message = result.error
                    await session.commit()
                    return

                if result.paused_for_review:
                    logger.info(
                        "workflow_paused_for_subtask_review",
                        task_id=task_id,
                    )
                    return

                logger.info(
                    "workflow_complete",
                    task_id=task_id,
                    status=task.status.value,
                    tasks_completed=result.tasks_completed,
                )

            except Exception as e:
                # =============================================================
                # GRACEFUL FAILURE HANDLING
                # =============================================================

                logger.exception(
                    "worker_task_error",
                    task_id=task_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"{type(e).__name__}: {str(e)}"
                    task.retry_count += 1
                    task.updated_at = datetime.utcnow()

                    # Log crash to AgentLog for SSE visibility
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
        # CRITICAL: Guard against engine being None
        if engine is not None:
            await engine.dispose()


async def _resume_task_async(task_id: str, approved: bool) -> None:
    """Resume a paused task after review."""
    from backend.app.db.models import TaskStatus

    engine = None
    try:
        engine = await _create_worker_engine()
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

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
        if engine is not None:
            await engine.dispose()


# =============================================================================
# Dramatiq Actors
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
