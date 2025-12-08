"""
Blackboard Service - The Neuro-Symbolic Knowledge Graph.

This service manages the "Shared Brain" of the agent system.
It allows tasks to read/write structured knowledge and inherits context
from parent tasks.
"""
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import KnowledgeNode, Task


class BlackboardService:
    """Service for managing knowledge nodes and context resolution."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_knowledge(
        self,
        task_id: UUID,
        key: str,
        value: Dict[str, Any],
        reasoning: str | None = None,
    ) -> KnowledgeNode:
        """
        Write a fact to the blackboard for a specific task.
        """
        # Check if node already exists for this task/key to update vs create
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.task_id == task_id,
            KnowledgeNode.key == key
        )
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()

        if node:
            node.value = value
            node.reasoning = reasoning
        else:
            node = KnowledgeNode(
                task_id=task_id,
                key=key,
                value=value,
                reasoning=reasoning
            )
            self.session.add(node)

        await self.session.flush()
        return node

    async def get_context(self, task_id: UUID) -> Dict[str, Any]:
        """
        Resolve the full context for a task.

        Algorithm:
        1. Fetch the task's lineage (Self -> Parent -> Parent's Parent -> Root).
        2. Iterate from Root -> Self.
        3. Merge knowledge nodes at each level.

        This ensures Child overrides Parent.
        """
        # 1. Fetch Lineage
        lineage = await self._get_task_lineage(task_id)

        context: Dict[str, Any] = {}

        # 2. Iterate Root -> Self
        # Lineage returns [Self, Parent, Grandparent], so valid need reversed
        for task in reversed(lineage):
            # Fetch nodes for this task
            stmt = select(KnowledgeNode).where(KnowledgeNode.task_id == task.id)
            result = await self.session.execute(stmt)
            nodes = result.scalars().all()

            for node in nodes:
                # 3. Merge (Child overrides Parent)
                # We store the full node value under the key
                # e.g. context['UserSchema'] = {...}
                context[node.key] = node.value

        return context

    async def _get_task_lineage(self, task_id: UUID) -> List[Task]:
        """
        Fetch the chain of tasks from current up to root.
        Returns ordered list: [Current, Parent, Grandparent...]
        """
        lineage = []
        current_id: UUID | None = task_id

        while current_id:
            stmt = select(Task).where(Task.id == current_id)
            result = await self.session.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                break

            lineage.append(task)
            current_id = task.parent_task_id

        return lineage
