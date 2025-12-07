"""
Tasks API - Task CRUD and Management

Endpoints for creating, reading, and managing tasks.
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db import Repository, Task, TaskStatus, get_session

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
    repo_result = await session.execute(
        select(Repository).where(Repository.id == task_in.repo_id)
    )
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

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Get a task by ID with its agent logs."""

    result = await session.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.agent_logs))
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
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
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
    await session.flush()

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

    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
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

    logger.info("task_cancelled", task_id=str(task_id))

    return {"message": "Task cancelled", "task_id": str(task_id)}


@router.post("/{task_id}/approve")
async def approve_task_plan(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a task plan and continue execution."""

    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task.status != TaskStatus.PLAN_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is not awaiting plan approval (status: {task.status})",
        )

    task.status = TaskStatus.EXECUTING

    # Resume worker execution
    from backend.app.workers.agent_runner import resume_task
    resume_task.send(str(task.id), approved=True)

    logger.info("task_plan_approved", task_id=str(task_id))

    return {"message": "Plan approved, execution continuing", "task_id": str(task_id)}
