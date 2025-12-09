"""
Streaming API - Real-time Updates via SSE (Redis Pub/Sub)

Server-Sent Events for pushing agent progress to the frontend.

ARCHITECTURE CHANGE (December 2025):
Previously, this module used database polling, which caused QueuePool exhaustion.
Now it uses Redis Pub/Sub:

OLD (BROKEN):
    while True:
        task = await db.execute(select(Task))  # DB connection held FOREVER
        await asyncio.sleep(1)

NEW (FIXED):
    # 1. Fetch initial data (quick DB query, then release connection)
    # 2. Subscribe to Redis channel (no DB connection)
    # 3. Yield events from Redis (lightweight)

This eliminates the connection leak that caused:
    sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.app.core.events import (
    get_event_bus,
    global_channel,
    task_channel,
)
from backend.app.db import AgentLog, Task, get_session

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# SSE Event Helpers
# =============================================================================


def sse_event(event: str, data: dict, id: str | None = None) -> dict:
    """Create an SSE event dict."""
    return {
        "event": event,
        "data": json.dumps(data),
        "id": id,
    }


# =============================================================================
# Initial Data Fetch (Quick DB Query, Then Release)
# =============================================================================


async def fetch_initial_task_state(
    task_id: UUID,
    session: AsyncSession,
    last_log_id: UUID | None = None,
) -> tuple[dict | None, list[dict], list[dict]]:
    """
    Fetch initial task state and any missed logs.

    This is a ONE-TIME query. The DB connection is released after this returns.
    All subsequent updates come from Redis pub/sub.

    Returns:
        Tuple of (task_state, missed_logs)
    """
    # Get task
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        return None, []

    task_state = {
        "task_id": str(task_id),
        "status": task.status.value,
        "current_agent": task.current_agent,
        "current_step": task.current_step,
    }

    # Get any logs created after last_log_id (for reconnection)
    # CRITICAL: Include logs from BOTH root task AND its subtasks
    # Frontend subscribes to root task, but logs are created with subtask IDs

    # Get subtask IDs for this root task
    subtask_query = select(Task.id).where(Task.parent_task_id == task_id)
    subtask_result = await session.execute(subtask_query)
    subtask_ids = [row[0] for row in subtask_result.fetchall()]

    # Query logs from root task OR any of its subtasks
    all_task_ids = [task_id] + subtask_ids
    log_query = (
        select(AgentLog).where(AgentLog.task_id.in_(all_task_ids)).order_by(AgentLog.created_at)
    )
    if last_log_id:
        log_query = log_query.where(AgentLog.id > last_log_id)

    log_result = await session.execute(log_query)
    logs = log_result.scalars().all()

    missed_logs = [
        {
            "id": str(log.id),
            "task_id": str(task_id),
            "agent_persona": log.agent_persona,
            "step_number": log.step_number,
            "ui_title": log.ui_title,
            "ui_subtitle": log.ui_subtitle,
            "confidence_score": log.confidence_score,
            "requires_review": log.requires_review,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

    # CRITICAL: Also fetch file changes from ChangeSet table
    from backend.app.db.models import ChangeSet

    changeset_query = (
        select(ChangeSet).where(ChangeSet.task_id.in_(all_task_ids)).order_by(ChangeSet.created_at)
    )
    changeset_result = await session.execute(changeset_query)
    changesets = changeset_result.scalars().all()

    file_changes = [
        {
            "id": str(cs.id),
            "task_id": str(cs.task_id),
            "file_path": cs.file_path,
            "file_action": cs.action,
            "byte_size": len(cs.diff) if cs.diff else 0,
            "created_at": cs.created_at.isoformat(),
        }
        for cs in changesets
    ]

    return task_state, missed_logs, file_changes


# =============================================================================
# SSE Generators (Redis-Based, Zero DB Usage)
# =============================================================================


async def task_event_generator(
    task_id: UUID,
    initial_state: dict,
    missed_logs: list[dict],
    file_changes: list[dict] = None,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for a task's progress.

    CRITICAL: This generator does NOT use any database connections.
    It only reads from Redis pub/sub.

    Flow:
    1. Yield initial state (from pre-fetched data)
    2. Yield any missed logs (from pre-fetched data)
    3. Yield any missed file changes
    4. Subscribe to Redis and yield new events
    """
    logger.info("sse_stream_started", task_id=str(task_id))

    # 1. Yield initial status
    yield sse_event("status", initial_state)

    # 2. Yield any missed logs (for reconnection support)
    for log in missed_logs:
        yield sse_event("agent_log", log, id=log["id"])

    # 3. Yield any missed file changes (for Files tab population)
    if file_changes:
        for fc in file_changes:
            yield sse_event("file_verified", fc, id=fc["id"])

    # 3. Subscribe to Redis channel and yield events
    event_bus = get_event_bus()
    channel = task_channel(str(task_id))

    try:
        async for event in event_bus.subscribe(channel):
            # Convert Redis event to SSE event
            yield sse_event(
                event=event.event_type,
                data=event.data,
                id=event.data.get("id"),
            )

            # Check for completion
            if event.event_type == "complete":
                logger.info("sse_stream_complete", task_id=str(task_id))
                break

    except asyncio.CancelledError:
        logger.info("sse_stream_cancelled", task_id=str(task_id))
        raise


async def global_event_generator() -> AsyncGenerator[dict, None]:
    """
    Generate SSE events for all task activity.

    CRITICAL: This generator does NOT use any database connections.
    It subscribes to the global Redis channel.
    """
    logger.info("global_sse_stream_started")

    event_bus = get_event_bus()

    try:
        async for event in event_bus.subscribe(global_channel()):
            yield sse_event(
                event=event.event_type,
                data=event.data,
                id=event.data.get("id"),
            )

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

    ARCHITECTURE:
    1. Quick initial fetch (DB connection used and RELEASED)
    2. SSE generator (uses Redis only, no DB)
    """
    # Parse last_event_id for reconnection
    last_log_id = None
    if last_event_id:
        try:
            last_log_id = UUID(last_event_id)
        except ValueError:
            pass

    # ONE-TIME DB query - connection is released after this
    initial_state, missed_logs, file_changes = await fetch_initial_task_state(
        task_id, session, last_log_id
    )

    if initial_state is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Return SSE response (generator uses Redis only)
    return EventSourceResponse(
        task_event_generator(task_id, initial_state, missed_logs, file_changes)
    )


@router.get("/global")
async def stream_global_events() -> EventSourceResponse:
    """
    Stream real-time events for all task activity.

    Useful for dashboards monitoring all agent operations.

    NOTE: No database dependency - streams directly from Redis.
    """
    return EventSourceResponse(global_event_generator())
