"""
Reasoner Core - Neuro-Symbolic Reasoning Engine with Memory

This module provides the integration point between the agent system and
the Mnemosyne memory subsystem. It enhances prompts with relevant past
experiences and stores new experiences after task execution.

The Reasoner wraps existing agent calls and provides:
1. Memory-augmented context building
2. Post-execution experience persistence
3. Safe fallback when memory system unavailable
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from gravity_core.llm import LLMClient
    from backend.app.db.models import Task
    from backend.app.services.memory_manager import MemoryManager


logger = structlog.get_logger(__name__)


class Reasoner:
    """
    Neuro-Symbolic Reasoning Engine with Long-Term Memory.

    Wraps agent execution to provide:
    - Memory-augmented prompts (recall relevant experiences)
    - Experience persistence (save outcomes for future learning)

    Usage:
        reasoner = Reasoner(session, llm_client)
        context = await reasoner.build_augmented_context(task, focus_files)
        # ... execute agent with context ...
        await reasoner.record_outcome(task, plan, "success")
    """

    def __init__(
        self,
        session: "AsyncSession",
        llm_client: "LLMClient",
    ):
        """
        Initialize the Reasoner with database session and LLM client.

        Args:
            session: SQLAlchemy async session for database access
            llm_client: LLMClient for embeddings and generation
        """
        self._session = session
        self._llm = llm_client
        self._memory: "MemoryManager | None" = None

    @property
    def memory(self) -> "MemoryManager":
        """Lazy initialization of MemoryManager."""
        if self._memory is None:
            from backend.app.services.memory_manager import MemoryManager
            self._memory = MemoryManager(self._session, self._llm)
        return self._memory

    async def build_augmented_context(
        self,
        task: "Task",
        focus_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Build context dictionary augmented with relevant memories.

        This method queries the memory system for relevant past experiences
        and includes them in the context for prompt building.

        Args:
            task: The current task being executed
            focus_files: List of files the task will work on

        Returns:
            Dict with 'memory_context' key containing relevant experiences
        """
        context: dict[str, Any] = {}

        try:
            memory_context = await self.memory.recall_context(
                task_desc=task.user_request or "",
                focus_files=focus_files,
            )

            if memory_context:
                context["memory_context"] = memory_context
                logger.info(
                    "reasoner_memory_injected",
                    task_id=str(task.id),
                    context_length=len(memory_context),
                )
            else:
                context["memory_context"] = ""
                logger.debug("reasoner_no_memories", task_id=str(task.id))

        except Exception as e:
            # Memory system failure should NOT block execution
            logger.warning(
                "reasoner_memory_recall_failed",
                task_id=str(task.id),
                error=str(e),
            )
            context["memory_context"] = ""

        return context

    async def record_outcome(
        self,
        task: "Task",
        plan: dict | None,
        outcome: str,
    ) -> None:
        """
        Record task outcome as an episodic memory.

        Should be called in a finally block after task execution,
        regardless of success or failure.

        Args:
            task: The completed task
            plan: The execution plan (if available)
            outcome: "success", "failure", or descriptive string
        """
        try:
            memory_id = await self.memory.save_experience(
                task=task,
                plan=plan,
                outcome=outcome,
            )

            if memory_id:
                logger.info(
                    "reasoner_experience_recorded",
                    task_id=str(task.id),
                    memory_id=memory_id,
                    outcome=outcome,
                )
            else:
                logger.warning(
                    "reasoner_experience_not_saved",
                    task_id=str(task.id),
                )

        except Exception as e:
            # Memory save failure should NOT crash the application
            logger.error(
                "reasoner_record_failed",
                task_id=str(task.id),
                error=str(e),
            )


def inject_memory_into_prompt(
    base_prompt: str,
    memory_context: str,
) -> str:
    """
    Inject memory context into an agent prompt.

    Utility function for prompt builders to add memory context
    without modifying the core prompt structure.

    Args:
        base_prompt: The original prompt
        memory_context: Retrieved memory context from recall_context()

    Returns:
        Enhanced prompt with memory section injected
    """
    if not memory_context:
        return base_prompt

    # Insert memory context before the main prompt content
    return f"""{memory_context}

---

{base_prompt}"""
