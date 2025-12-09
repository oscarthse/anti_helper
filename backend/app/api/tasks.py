"""
Tasks API - Task CRUD and Management

Endpoints for creating, reading, and managing tasks.
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db import Repository, Task, TaskDependency, TaskStatus, get_session

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class TaskCreate(BaseModel):
    """Request schema for creating a task."""

    repo_id: UUID = Field(description="Repository ID to operate on")
    user_request: str = Field(
        description="Natural language description of the task",
        min_length=10,
    )
    title: str | None = Field(
        default=None,
        description="Optional task title",
    )


class TaskResponse(BaseModel):
    """Response schema for a task."""

    id: UUID
    repo_id: UUID
    user_request: str
    title: str | None
    status: TaskStatus
    current_agent: str | None
    current_step: int
    task_plan: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class AgentLogResponse(BaseModel):
    """Response schema for an agent log entry."""

    id: UUID
    agent_persona: str
    step_number: int
    ui_title: str
    ui_subtitle: str
    confidence_score: float
    requires_review: bool
    created_at: datetime
    created_at: datetime
    duration_ms: int | None
    technical_reasoning: str | None
    tool_calls: list[dict] | None

    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    """Detailed task response including agent logs."""

    agent_logs: list[AgentLogResponse]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """
    Create a new task.

    This creates the task in PENDING status. Call the execute endpoint
    or wait for a worker to pick it up for processing.
    """
    logger.info("creating_task", repo_id=str(task_in.repo_id))

    # Verify repository exists
    repo_result = await session.execute(select(Repository).where(Repository.id == task_in.repo_id))
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {task_in.repo_id} not found",
        )

    # Create task
    task = Task(
        repo_id=task_in.repo_id,
        user_request=task_in.user_request,
        title=task_in.title,
        status=TaskStatus.PENDING,
    )

    session.add(task)
    await session.flush()
    await session.refresh(task)

    logger.info("task_created", task_id=str(task.id))

    # Dispatch to worker queue
    from backend.app.workers.agent_runner import run_task

    run_task.send(str(task.id))

    return task


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    repo_id: UUID | None = None,
    parent_task_id: UUID | None = None,  # Start supporting hierarchical fetch
    status_filter: TaskStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    """List tasks with optional filtering."""

    query = select(Task).order_by(Task.created_at.desc())

    if repo_id:
        query = query.where(Task.repo_id == repo_id)
    if status_filter:
        query = query.where(Task.status == status_filter)

    # SYSTEM 3: Hierarchical View
    if parent_task_id:
        # If specifically asking for subtasks, verify them
        query = query.where(Task.parent_task_id == parent_task_id)
        # We might want to sort subtasks by creation order (FIFO) instead of DESC?
        # Actually usually easier to read top-down.
        query = query.order_by(Task.created_at.asc())
    else:
        # Default behavior: Show ONLY Root Tasks
        query = query.where(Task.parent_task_id.is_(None))

    query = query.limit(limit).offset(offset)

    # We need to execute a new query because the order_by might have changed
    # Logic above appended order_by asc to desc? SQLAlchemy handles this but safer to be clean.
    # Actually, the first order_by is global.

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Get a task by ID with its agent logs."""

    result = await session.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.agent_logs))
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return task


@router.post("/{task_id}/execute")
async def execute_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Trigger execution of a task.

    This dispatches the task to the worker queue.
    """
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status not in [TaskStatus.PENDING, TaskStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is in {task.status} state and cannot be executed",
        )

    # Update status
    task.status = TaskStatus.PLANNING
    await session.commit()

    # Dispatch to worker
    from backend.app.workers.agent_runner import run_task

    run_task.send(str(task.id))

    logger.info("task_execution_triggered", task_id=str(task_id))

    return {"message": "Task execution started", "task_id": str(task_id)}


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cancel a running task."""

    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed or failed task",
        )

    task.status = TaskStatus.FAILED
    task.error_message = "Cancelled by user"
    await session.commit()

    logger.info("task_cancelled", task_id=str(task_id))

    return {"message": "Task cancelled", "task_id": str(task_id)}


@router.post("/{task_id}/approve")
async def approve_task_plan(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a task plan and continue execution."""

    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Accept both review states
    if task.status not in (TaskStatus.PLAN_REVIEW, TaskStatus.REVIEW_REQUIRED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is not awaiting plan approval (status: {task.status})",
        )

    task.status = TaskStatus.EXECUTING
    await session.commit()

    # Resume worker execution
    from backend.app.workers.agent_runner import resume_task

    resume_task.send(str(task.id), approved=True)

    logger.info("task_plan_approved", task_id=str(task_id))

    return {"message": "Plan approved, execution continuing", "task_id": str(task_id)}


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Pause a running task."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Allow pausing from any active state
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Cannot pause a finished task")

    task.status = TaskStatus.PAUSED
    await session.commit()
    logger.info("task_paused", task_id=str(task_id))
    return {"message": "Task paused", "task_id": str(task_id)}


@router.post("/{task_id}/resume")
async def resume_task_endpoint(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resume a paused task."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.PAUSED:
        raise HTTPException(status_code=400, detail=f"Task is not paused (status: {task.status})")

    # Resume to PENDING to trigger Scheduler re-evaluation
    # If it was EXECUTING, it will be picked up again.
    task.status = TaskStatus.PENDING
    await session.commit()

    # Ensure worker is running (dispatch just in case, though polling might catch it)
    # Actually, we should check if worker is alive. But sending a message is safe.
    # If using pure DAG loop, we rely on the loop being alive.
    # BUT, if the loop was sleeping/paused, we need to wake it up?
    # For now, let's assume the Runner Loop is checking status.
    # WAIT: If the runner loop checks status, it needs to be running.
    # If we PAUSED via API, the Runner sees PAUSED and sleeps.
    # If we RESUME via API, the Runner sees PENDING (or EXECUTING?) and continues.
    # Setting to PENDING is safe.

    logger.info("task_resumed", task_id=str(task_id))
    return {"message": "Task resumed", "task_id": str(task_id)}


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a task and ALL associated data:
    - All subtasks (child tasks)
    - All agent logs
    - All knowledge nodes
    - All task dependencies

    This is a complete removal - as if the task never existed.
    """
    from backend.app.db import AgentLog, KnowledgeNode

    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Get all subtask IDs (recursive via parent_task_id)
    subtask_ids_result = await session.execute(
        select(Task.id).where(Task.parent_task_id == task_id)
    )
    subtask_ids = [row[0] for row in subtask_ids_result.fetchall()]

    # All task IDs to delete (root + subtasks)
    all_task_ids = [task_id] + subtask_ids

    logger.info(
        "deleting_task_cascade",
        root_task_id=str(task_id),
        subtask_count=len(subtask_ids),
        total_tasks=len(all_task_ids),
    )

    # 1. Delete agent logs for all tasks
    await session.execute(delete(AgentLog).where(AgentLog.task_id.in_(all_task_ids)))

    # 2. Delete knowledge nodes for all tasks
    await session.execute(delete(KnowledgeNode).where(KnowledgeNode.task_id.in_(all_task_ids)))

    # 3. Delete dependencies involving any of these tasks
    await session.execute(
        delete(TaskDependency).where(
            (TaskDependency.blocker_task_id.in_(all_task_ids))
            | (TaskDependency.blocked_task_id.in_(all_task_ids))
        )
    )

    # 4. Delete subtasks first (FK constraint)
    await session.execute(delete(Task).where(Task.parent_task_id == task_id))

    # 5. Delete root task
    await session.delete(task)
    await session.commit()

    logger.info("task_deleted_completely", task_id=str(task_id))
