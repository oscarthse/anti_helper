"""
Dashboard API - The Glass Cockpit
Status: LIVE (Phase V)

This router provides the "Truth-First" observability layer.
It bypasses the LLM stream and reads directly from the State Machine (PostgreSQL).
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.db.models import AgentLog, Task, TaskDependency, TaskStatus

logger = structlog.get_logger()

router = APIRouter()

# =============================================================================
# Models (The Protocol)
# =============================================================================


class DAGEdge(BaseModel):
    blocker_id: UUID
    blocked_id: UUID
    reason: str | None


class DAGNode(BaseModel):
    id: UUID
    title: str | None
    status: TaskStatus
    parent_id: UUID | None
    retry_count: int
    definition_of_done: dict[str, Any] | None
    # For UI Viz
    agent: str | None

    class Config:
        from_attributes = True


class DAGState(BaseModel):
    """The Full Truth of the System State."""

    root_task_id: UUID
    tasks: list[DAGNode]
    edges: list[DAGEdge]
    updated_at: datetime


class DashboardEvent(BaseModel):
    """Structured Log for the Event Stream."""

    id: UUID
    type: str  # SCHEDULER, REFEREE, LINTER, AGENT
    subtype: str | None  # REJECTION, SELECTION, etc.
    message: str
    timestamp: datetime
    metadata: dict[str, Any] | None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{root_task_id}/state", response_model=DAGState)
async def get_dag_state(
    root_task_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Get the full Topological State of the project.
    """
    # 1. Fetch all tasks in the lineage
    # Assuming shallow for now, or recursive query if needed.
    # Current model allows single-level parent.
    # For now, fetch all tasks where parent_id = root or id = root

    # Simple query: Fetch ALL tasks for this repo? Or just this tree?
    # We'll assume root_task_id is the main task.

    stmt_tasks = select(Task).where(
        (Task.id == root_task_id) | (Task.parent_task_id == root_task_id)
    )
    result_tasks = await session.execute(stmt_tasks)
    tasks = result_tasks.scalars().all()

    if not tasks:
        raise HTTPException(status_code=404, detail="Root task not found")

    task_ids = [t.id for t in tasks]

    # 2. Fetch dependencies
    stmt_edges = select(TaskDependency).where(
        (TaskDependency.blocker_task_id.in_(task_ids))
        | (TaskDependency.blocked_task_id.in_(task_ids))
    )
    result_edges = await session.execute(stmt_edges)
    edges = result_edges.scalars().all()

    # 3. Assemble
    dag_nodes = [
        DAGNode(
            id=t.id,
            title=t.title or t.user_request[:50],
            status=t.status,
            parent_id=t.parent_task_id,
            retry_count=getattr(t, "retry_count", 0),
            definition_of_done=getattr(t, "definition_of_done", None),
            agent=t.current_agent,
        )
        for t in tasks
    ]

    dag_edges = [
        DAGEdge(blocker_id=e.blocker_task_id, blocked_id=e.blocked_task_id, reason=e.reason)
        for e in edges
    ]

    return DAGState(
        root_task_id=root_task_id, tasks=dag_nodes, edges=dag_edges, updated_at=datetime.utcnow()
    )


@router.get("/{root_task_id}/events", response_model=list[DashboardEvent])
async def get_dashboard_events(
    root_task_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """
    Get structured logs for the UI.
    Maps AgentLog entries to DashboardEvents.
    """
    # Fetch logs for all tasks in this tree
    # Subquery for task IDs
    subq = select(Task.id).where((Task.id == root_task_id) | (Task.parent_task_id == root_task_id))

    stmt = (
        select(AgentLog)
        .where(AgentLog.task_id.in_(subq))
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    logs = result.scalars().all()

    events = []
    for log in logs:
        # Heuristic mapping for now
        evt_type = "AGENT"
        if log.agent_persona == "system":
            evt_type = "SYSTEM"  # Could be SCHEDULER or REFEREE if we parsed log content

        # In future, AgentLog should have event_type column.
        # For now, we infer from title/subtitle

        events.append(
            DashboardEvent(
                id=log.id,
                type=evt_type,
                subtype=None,
                message=f"[{log.ui_title}] {log.ui_subtitle}",
                timestamp=log.created_at,
                metadata={"step": log.step_number, "requires_review": log.requires_review},
            )
        )

    return events


@router.websocket("/{root_task_id}/stream")
async def websocket_dashboard_stream(
    websocket: WebSocket, root_task_id: UUID, session: AsyncSession = Depends(get_session)
):
    """
    Real-time State Push.
    Polls the DB every 1s and sends 'STATE_UPDATE' if something changed.
    """
    await websocket.accept()

    last_hash = ""

    try:
        while True:
            # 1. Fetch State (Re-using logic from get_dag_state effectively)
            # To be efficient, maybe just check MAX(updated_at)?
            # Models don't have updated_at on all tables reliably? Task does.

            stmt = (
                select(Task.updated_at)
                .where((Task.id == root_task_id) | (Task.parent_task_id == root_task_id))
                .order_by(Task.updated_at.desc())
                .limit(1)
            )

            result = await session.execute(stmt)
            latest_update = result.scalar_one_or_none()

            current_hash = str(latest_update) if latest_update else "null"

            if current_hash != last_hash:
                # State Changed! Send full state for now (Simpler than Delta)
                # Call internal helper or just re-query.
                # Re-querying is robust.

                # ... (Logic from get_dag_state) ...
                stmt_tasks = select(Task).where(
                    (Task.id == root_task_id) | (Task.parent_task_id == root_task_id)
                )
                tasks = (await session.execute(stmt_tasks)).scalars().all()
                task_ids = [t.id for t in tasks]

                stmt_edges = select(TaskDependency).where(
                    (TaskDependency.blocker_task_id.in_(task_ids))
                    | (TaskDependency.blocked_task_id.in_(task_ids))
                )
                edges = (await session.execute(stmt_edges)).scalars().all()

                dag_nodes = [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "status": t.status.value,
                        "retry_count": getattr(t, "retry_count", 0),
                        "agent": t.current_agent,
                    }
                    for t in tasks
                ]

                payload = {
                    "type": "STATE_UPDATE",
                    "data": {
                        "tasks": dag_nodes,
                        "edges": [
                            {"blocker": str(e.blocker_task_id), "blocked": str(e.blocked_task_id)}
                            for e in edges
                        ],
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }

                await websocket.send_json(payload)
                last_hash = current_hash

            await asyncio.sleep(1)  # Pulse

    except WebSocketDisconnect:
        logger.info("dashboard_ws_disconnect", root_task_id=str(root_task_id))
    except Exception as e:
        logger.error("dashboard_ws_error", error=str(e))
        await websocket.close()
