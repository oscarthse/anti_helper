"""
Topological Scheduler Service.

This module implements the "Dynamic Nervous System" logic.
It replaces linear execution with a graph-based dependency solver.
"""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Task, TaskDependency, TaskStatus


class SchedulerService:
    """
    Topological Scheduler for the Agent Nervous System.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_next_executable_tasks(self, root_task_id: UUID) -> list[Task]:
        """
        Get all tasks that are ready to run.

        Definition of 'Ready':
        1. Status is PENDING
        2. Is a subtask of the given root_task_id
        3. All 'blocker' dependencies have Status == COMPLETED

        This effectively performs a topological sort query on the fly.
        """
        # Logic for finding ready subtasks:
        # We want Tasks where:
        # We want SubTasks where:
        # - parent_task_id == root_task_id
        # - status == PENDING
        # - NOT EXISTS (Dependency where blocked_id == SubTask.id AND blocker.status != COMPLETED)

        # Let's verify this logic.
        # If I have 0 dependencies, the NOT EXISTS clause is True. -> Ready.
        # If I have 1 dependency and it is COMPLETED, NOT EXISTS is True (no non-completed blockers). -> Ready.
        # If I have 1 dependency and it is PENDING, NOT EXISTS is False (found a non-completed blocker). -> Blocked.

        # Subquery: Find dependencies that are NOT completed
        # This returns the set of 'Edges' that serve as active blocks.
        active_blockers_subquery = (
            select(TaskDependency.blocked_task_id)
            .join(Task, TaskDependency.blocker_task_id == Task.id)
            .where(Task.status != TaskStatus.COMPLETED)
            .scalar_subquery()
        )

        # Main Query
        stmt = (
            select(Task)
            .where(
                and_(
                    Task.parent_task_id == root_task_id,
                    Task.status == TaskStatus.PENDING,
                    Task.id.not_in(active_blockers_subquery),
                )
            )
            .options(
                # Eager load dependencies to be safe/useful for the caller
                selectinload(Task.knowledge_nodes)
            )
        )

        result = await self.session.execute(stmt)
        executable_tasks = result.scalars().all()

        return list(executable_tasks)

    async def get_task_bottlenecks(self, root_task_id: UUID) -> list[tuple[str, int]]:
        """
        Diagnostic: Identify which tasks are blocking the most downstream work.
        Returns [(TaskTitle, NumberOfBlockedTasks), ...]
        """
        stmt = (
            select(Task.title, func.count(TaskDependency.blocked_task_id).label("blocked_count"))
            .join(TaskDependency, Task.id == TaskDependency.blocker_task_id)
            .where(Task.parent_task_id == root_task_id, Task.status != TaskStatus.COMPLETED)
            .group_by(Task.title)
            .order_by(func.count(TaskDependency.blocked_task_id).desc())
        )

        result = await self.session.execute(stmt)
        return result.all()
