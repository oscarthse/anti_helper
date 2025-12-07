"""
Streaming API - Real-time Updates via SSE

Server-Sent Events for pushing agent progress to the frontend.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.app.db import AgentLog, Task, get_session

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Event Types
# =============================================================================


class SSEEvent:
    """Represents an SSE event."""

    def __init__(
        self,
        event: str,
        data: dict,
        id: str | None = None,
    ) -> None:
        self.event = event
        self.data = data
        self.id = id

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "data": json.dumps(self.data),
            "id": self.id,
        }


# =============================================================================
# SSE Generators
# =============================================================================


async def task_event_generator(
    task_id: UUID,
    session: AsyncSession,
    last_event_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for a task's progress.

    This polls the database for new agent logs and status changes.
    In production, this would use Redis pub/sub or PostgreSQL LISTEN/NOTIFY.
    """
    logger.info("sse_stream_started", task_id=str(task_id))

    last_log_id = None
    if last_event_id:
        try:
            last_log_id = UUID(last_event_id)
        except ValueError:
            pass

    last_status = None

    try:
        while True:
            # Get current task state
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                yield SSEEvent(
                    event="error",
                    data={"message": f"Task {task_id} not found"},
                ).to_dict()
                break

            # Emit status change event
            if task.status != last_status:
                yield SSEEvent(
                    event="status",
                    data={
                        "task_id": str(task_id),
                        "status": task.status.value,
                        "current_agent": task.current_agent,
                        "current_step": task.current_step,
                    },
                ).to_dict()
                last_status = task.status

            # Get new agent logs
            log_query = (
                select(AgentLog)
                .where(AgentLog.task_id == task_id)
                .order_by(AgentLog.created_at)
            )
            if last_log_id:
                log_query = log_query.where(AgentLog.id > last_log_id)

            log_result = await session.execute(log_query)
            new_logs = log_result.scalars().all()

            for log in new_logs:
                yield SSEEvent(
                    event="agent_log",
                    data={
                        "id": str(log.id),
                        "task_id": str(task_id),
                        "agent_persona": log.agent_persona,
                        "step_number": log.step_number,
                        "ui_title": log.ui_title,
                        "ui_subtitle": log.ui_subtitle,
                        "confidence_score": log.confidence_score,
                        "requires_review": log.requires_review,
                        "created_at": log.created_at.isoformat(),
                    },
                    id=str(log.id),
                ).to_dict()
                last_log_id = log.id

            # Check if task is complete
            if task.status in [task.status.COMPLETED, task.status.FAILED]:
                yield SSEEvent(
                    event="complete",
                    data={
                        "task_id": str(task_id),
                        "status": task.status.value,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    },
                ).to_dict()
                break

            # Poll interval
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("sse_stream_cancelled", task_id=str(task_id))
        raise


async def global_event_generator(
    session: AsyncSession,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for all task activity.

    Useful for dashboard views showing all agent activity.
    """
    logger.info("global_sse_stream_started")

    last_check = datetime.utcnow()

    try:
        while True:
            # Get recent activity
            result = await session.execute(
                select(AgentLog)
                .where(AgentLog.created_at > last_check)
                .order_by(AgentLog.created_at)
                .limit(50)
            )
            new_logs = result.scalars().all()

            for log in new_logs:
                yield SSEEvent(
                    event="agent_log",
                    data={
                        "id": str(log.id),
                        "task_id": str(log.task_id),
                        "agent_persona": log.agent_persona,
                        "ui_title": log.ui_title,
                        "ui_subtitle": log.ui_subtitle,
                        "created_at": log.created_at.isoformat(),
                    },
                    id=str(log.id),
                ).to_dict()

            if new_logs:
                last_check = new_logs[-1].created_at

            await asyncio.sleep(2)

    except asyncio.CancelledError:
        logger.info("global_sse_stream_cancelled")
        raise


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/task/{task_id}")
async def stream_task_events(
    task_id: UUID,
    last_event_id: str | None = Query(None, alias="Last-Event-ID"),
    session: AsyncSession = Depends(get_session),
) -> EventSourceResponse:
    """
    Stream real-time events for a specific task.

    Events:
    - status: Task status changed
    - agent_log: New agent action logged
    - complete: Task finished (success or failure)
    - error: An error occurred

    Supports reconnection via Last-Event-ID header.
    """
    # Verify task exists
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return EventSourceResponse(
        task_event_generator(task_id, session, last_event_id)
    )


@router.get("/global")
async def stream_global_events(
    session: AsyncSession = Depends(get_session),
) -> EventSourceResponse:
    """
    Stream real-time events for all task activity.

    Useful for dashboards monitoring all agent operations.
    """
    return EventSourceResponse(
        global_event_generator(session)
    )
