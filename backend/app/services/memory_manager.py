"""
Memory Manager - Long-Term Episodic Memory for Agents (Mnemosyne)

This service provides the "Hippocampus" for the agent system:
- Stores task experiences as embeddings for semantic search
- Links memories to code artifacts (files, symbols) for graph retrieval
- Implements hybrid search combining vector similarity + symbolic anchors

Usage:
    memory = MemoryManager(session, llm_client)

    # After task completion
    await memory.save_experience(task, plan, "success")

    # Before planning
    context = await memory.recall_context("Add user authentication", ["auth.py"])
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from gravity_core.llm import LLMClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.db.models import Task


logger = structlog.get_logger(__name__)


# Maximum characters to send for summarization (prevent context overflow)
MAX_CONTENT_CHARS = 10000

# Causal summary prompt template
CAUSAL_SUMMARY_PROMPT = (
    """You are summarizing a completed software engineering task for future reference.

## Task Request
{task_request}

## Execution Plan
{plan_summary}

## Outcome
{outcome}

## Files Affected
{files_affected}

---

Generate a concise **causal summary** (2-3 sentences) that captures:
1. WHAT was done (the change)
2. WHY it was done (the intent)
3. HOW it was achieved (key techniques/patterns used)

Focus on lessons that would help with similar future tasks.
Output ONLY the summary text, no JSON or formatting."""
)


class MemoryManager:
    """
    Long-term memory storage and retrieval for agent experiences.

    Implements the Mnemosyne Protocol:
    - Episodic memory: Store task outcomes with semantic embeddings
    - Symbolic anchors: Link memories to code artifacts
    - Hybrid retrieval: Combine vector search + anchor matching
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_client: LLMClient,
    ):
        """
        Initialize the Memory Manager.

        Args:
            session: SQLAlchemy async session for database operations
            llm_client: LLMClient instance for embeddings and summarization
        """
        self._session = session
        self._llm = llm_client

    async def save_experience(
        self,
        task: Task,
        plan: dict | None,
        outcome: str,
    ) -> str | None:
        """
        Save a task execution as an episodic memory.

        Process:
        1. Summarize the task/plan/outcome using gpt-4o-mini
        2. Generate embedding of the summary
        3. Store in memories table
        4. Extract file paths and create symbolic anchors

        Args:
            task: The completed Task object
            plan: The TaskPlan dict (or None if planning failed)
            outcome: "success", "failure", or custom outcome description

        Returns:
            Memory ID as string, or None if save failed

        Note:
            This method is safe to call even if the memory system is unavailable.
            It will log warnings but not raise exceptions.
        """
        try:
            from backend.app.db.models import Memory, MemoryAnchor

            # Extract relevant content
            task_request = (task.user_request or "")[:MAX_CONTENT_CHARS]
            plan_summary = ""
            files_affected = []

            if plan:
                # Extract plan metadata
                steps = plan.get("steps", [])
                plan_summary = "\n".join(
                    f"- {s.get('title', 'Untitled')}: {s.get('description', '')[:200]}"
                    for s in steps[:10]
                )[:MAX_CONTENT_CHARS]

                # Collect all affected files
                for step in steps:
                    files_affected.extend(step.get("files_affected", []))

            # Generate causal summary via LLM
            summary_prompt = CAUSAL_SUMMARY_PROMPT.format(
                task_request=task_request,
                plan_summary=plan_summary or "(No plan available)",
                outcome=outcome,
                files_affected=", ".join(files_affected[:20]) or "(None)",
            )

            try:
                # Use a simple pydantic-free call for summarization
                from pydantic import BaseModel

                class SummaryResponse(BaseModel):
                    ui_title: str = "Memory Summary"
                    ui_subtitle: str = ""
                    technical_reasoning: str = ""
                    confidence_score: float = 1.0

                summary_result = await self._llm.generate_structured_output(
                    prompt=summary_prompt,
                    output_schema=SummaryResponse,
                    model_name="gpt-4o-mini",
                    temperature=0.3,
                )
                summary = summary_result.technical_reasoning or summary_result.ui_subtitle
            except Exception as e:
                logger.warning("memory_summarization_failed", error=str(e))
                # Fallback: use task request as summary
                summary = f"Task: {task_request[:500]}. Outcome: {outcome}"

            # Generate embedding
            try:
                embedding = await self._llm.embed_text(summary)
            except Exception as e:
                logger.warning("memory_embedding_failed", error=str(e))
                embedding = None

            # Create memory record
            memory = Memory(
                id=uuid4(),
                content=json.dumps({
                    "task_request": task_request,
                    "plan_summary": plan_summary,
                    "outcome": outcome,
                }),
                summary=summary,
                embedding=embedding,
                memory_type=f"task_{outcome}",
                confidence=0.9 if outcome == "success" else 0.6,
                task_id=task.id,
                created_at=datetime.utcnow(),
            )
            self._session.add(memory)

            # Create anchors for affected files
            for file_path in set(files_affected):
                # Strip [NEW] prefix if present
                clean_path = file_path.replace("[NEW] ", "").strip()
                if clean_path:
                    anchor = MemoryAnchor(
                        id=uuid4(),
                        memory_id=memory.id,
                        file_path=clean_path,
                        created_at=datetime.utcnow(),
                    )
                    self._session.add(anchor)

            await self._session.commit()

            logger.info(
                "memory_saved",
                memory_id=str(memory.id),
                outcome=outcome,
                anchors=len(files_affected),
            )
            return str(memory.id)

        except Exception as e:
            logger.error("memory_save_failed", error=str(e))
            await self._session.rollback()
            return None

    async def recall_context(
        self,
        task_desc: str,
        focus_files: list[str] | None = None,
        top_k: int = 5,
    ) -> str:
        """
        Retrieve relevant memories for context injection.

        Uses hybrid search combining:
        - Vector similarity (cosine distance)
        - Anchor matching (file path overlap)
        - Confidence weighting

        The Effective Rank formula:
            score = (1 - cosine_distance) * confidence + anchor_bonus

        Args:
            task_desc: Description of the current task
            focus_files: List of files the current task will work on
            top_k: Maximum number of memories to return

        Returns:
            Formatted string of relevant memories for prompt injection,
            or empty string if no relevant memories found

        Note:
            This method is safe to call even if the memory system is unavailable.
            It will return an empty string rather than raising exceptions.
        """
        try:
            from sqlalchemy import text

            # Generate query embedding
            try:
                query_embedding = await self._llm.embed_text(task_desc)
            except Exception as e:
                logger.warning("recall_embedding_failed", error=str(e))
                return ""

            # Prepare file list for anchor matching
            files_array = focus_files or []

            # Execute hybrid search query
            query = text("""
                WITH scored_memories AS (
                    SELECT
                        m.id,
                        m.content,
                        m.summary,
                        m.confidence,
                        m.memory_type,
                        m.created_at,
                        -- Vector similarity (1 - cosine distance)
                        CASE
                            WHEN m.embedding IS NOT NULL
                            THEN 1 - (m.embedding <=> :query_embedding::vector)
                            ELSE 0
                        END AS vector_score,
                        -- Anchor bonus: +0.3 per matching file
                        COALESCE(
                            (SELECT COUNT(*) * 0.3
                             FROM memory_anchors a
                             WHERE a.memory_id = m.id
                             AND a.file_path = ANY(:files)),
                            0
                        ) AS anchor_bonus
                    FROM memories m
                    WHERE m.embedding IS NOT NULL
                )
                SELECT
                    id,
                    summary,
                    memory_type,
                    vector_score,
                    anchor_bonus,
                    (vector_score * confidence + anchor_bonus) AS effective_rank
                FROM scored_memories
                WHERE vector_score > 0.3 OR anchor_bonus > 0
                ORDER BY effective_rank DESC
                LIMIT :limit
            """)

            result = await self._session.execute(
                query,
                {
                    "query_embedding": str(query_embedding),
                    "files": files_array,
                    "limit": top_k,
                },
            )
            rows = result.fetchall()

            if not rows:
                logger.debug("recall_no_memories_found", task_desc=task_desc[:100])
                return ""

            # Format memories for prompt injection
            memories_text = []
            for row in rows:
                memory_id, summary, memory_type, vector_score, anchor_bonus, rank = row
                emoji = "✅" if "success" in memory_type else "⚠️"
                memories_text.append(
                    f"{emoji} [{memory_type}] (relevance: {rank:.2f})\n   {summary}"
                )

            formatted = "\n".join(memories_text)
            logger.info(
                "recall_memories_retrieved",
                count=len(rows),
                top_score=rows[0][-1] if rows else 0,
            )

            return f"""## Relevant Past Experiences
{formatted}
"""

        except Exception as e:
            logger.error("recall_failed", error=str(e))
            return ""
