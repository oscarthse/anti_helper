"""
DAG Executor Service - The Topological Workflow Engine

This module implements a clean, class-based DAG executor that replaces
the previous 175-line while loop. It handles:
- Topological task scheduling
- Pause/Resume signals
- Timeout enforcement
- Referee validation
- Clean error propagation

Architecture:
    DAGExecutor orchestrates the workflow
    SchedulerService provides ready tasks
    Referee validates completed work
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Task, TaskStatus
from backend.app.services.scheduler import SchedulerService

logger = structlog.get_logger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class ExecutionResult:
    """Result of DAG execution."""

    success: bool
    error: str | None = None
    tasks_completed: int = 0
    paused_for_review: bool = False


@dataclass
class TaskExecutionResult:
    """Result of single task execution."""

    success: bool
    error: str | None = None
    requires_review: bool = False
    changeset: dict = field(default_factory=dict)


# =============================================================================
# DAG Executor
# =============================================================================


class DAGExecutor:
    """
    Topological DAG executor with clean separation of concerns.

    Responsibilities:
    1. Poll scheduler for ready tasks
    2. Dispatch individual task execution
    3. Validate via Referee
    4. Handle pause/resume signals
    5. Enforce timeouts

    Usage:
        executor = DAGExecutor(session, root_task, repo)
        result = await executor.execute(context)
    """

    # Configuration
    TIMEOUT_SECONDS: int = 600  # 10 minutes
    PAUSE_CHECK_INTERVAL: float = 5.0  # Check pause status every 5s
    POLL_INTERVAL: float = 2.0  # Poll for ready tasks every 2s
    MAX_RETRIES: int = 3  # Max retry attempts per task

    def __init__(
        self,
        session: AsyncSession,
        root_task: Task,
        repo: Any,  # Repository model
        context: dict[str, Any],
    ) -> None:
        """
        Initialize the DAG executor.

        Args:
            session: Database session
            root_task: The root task whose subtasks form the DAG
            repo: Repository model with path info
            context: Execution context (user_request, etc.)
        """
        self.session = session
        self.root_task = root_task
        self.repo = repo
        self.context = context

        self.scheduler = SchedulerService(session)
        self._start_time = datetime.now(UTC)
        self._tasks_completed = 0
        self._loop_iterations = 0

        # Lazy import to avoid circular imports
        self._referee = None

        logger.info(
            "dag_executor_initialized",
            root_task_id=str(root_task.id),
            repo_path=repo.path,
        )

    @property
    def referee(self):
        """Lazy-load Referee to avoid import issues."""
        if self._referee is None:
            from gravity_core.guardrails.referee import Referee

            self._referee = Referee(self.repo.path)
        return self._referee

    # =========================================================================
    # Main Execution Loop
    # =========================================================================

    async def execute(self) -> ExecutionResult:
        """
        Execute the DAG workflow.

        Returns:
            ExecutionResult with success status, error details, and metrics
        """
        logger.info("dag_execution_started", root_task_id=str(self.root_task.id))

        try:
            while not self._is_timed_out():
                self._loop_iterations += 1

                # ---------------------------------------------------------
                # Signal Check: Pause/Resume/Terminate
                # ---------------------------------------------------------
                signal = await self._check_signals()

                if signal == "PAUSED":
                    logger.info("dag_executor_paused", root_task_id=str(self.root_task.id))
                    await self._wait_for_resume()
                    continue

                elif signal == "TERMINATED":
                    logger.info("dag_executor_terminated", root_task_id=str(self.root_task.id))
                    return ExecutionResult(
                        success=False,
                        error="Task was terminated by user.",
                        tasks_completed=self._tasks_completed,
                    )

                # ---------------------------------------------------------
                # Poll Scheduler for Ready Tasks
                # ---------------------------------------------------------
                ready_tasks = await self.scheduler.get_next_executable_tasks(self.root_task.id)

                if not ready_tasks:
                    # No tasks ready - check if we're done or waiting
                    if await self._all_tasks_complete():
                        logger.info(
                            "dag_execution_victory",
                            root_task_id=str(self.root_task.id),
                            tasks_completed=self._tasks_completed,
                            loop_iterations=self._loop_iterations,
                        )
                        break  # VICTORY - all tasks complete

                    # Tasks remaining but none ready - waiting on dependencies
                    logger.debug(
                        "dag_executor_waiting",
                        root_task_id=str(self.root_task.id),
                    )
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue

                # ---------------------------------------------------------
                # Execute Next Ready Task
                # ---------------------------------------------------------
                current_task = ready_tasks[0]  # Take first ready task

                logger.info(
                    "dag_executor_dispatching",
                    task_id=str(current_task.id),
                    title=current_task.title,
                )

                # Execute with proper error handling to prevent stuck EXECUTING status
                try:
                    result = await self._execute_and_validate(current_task)
                except Exception as e:
                    # CRITICAL: Mark task as FAILED if execution crashes
                    logger.exception(
                        "task_execution_crashed",
                        task_id=str(current_task.id),
                        title=current_task.title,
                        error=str(e),
                    )
                    current_task.status = TaskStatus.FAILED
                    current_task.error_message = f"Execution crashed: {type(e).__name__}: {str(e)}"
                    await self.session.commit()

                    # Continue to next task instead of blocking the whole DAG
                    continue

                # Check if review is required - pause workflow
                if result.requires_review:
                    logger.info(
                        "dag_executor_paused_for_review",
                        task_id=str(current_task.id),
                    )
                    return ExecutionResult(
                        success=True,
                        paused_for_review=True,
                        tasks_completed=self._tasks_completed,
                    )

                # Check for failure
                if not result.success:
                    return ExecutionResult(
                        success=False,
                        error=f"Task '{current_task.title}' failed: {result.error}",
                        tasks_completed=self._tasks_completed,
                    )

                self._tasks_completed += 1

                # CRITICAL: Update root task progress in DB for frontend
                self.root_task.current_step = self._tasks_completed
                await self.session.commit()

            # Check for timeout
            if self._is_timed_out():
                return ExecutionResult(
                    success=False,
                    error=f"Emergency Stop: Workflow timed out after {self.TIMEOUT_SECONDS}s",
                    tasks_completed=self._tasks_completed,
                )

            # ---------------------------------------------------------
            # Documentation Phase (after all tasks complete)
            # ---------------------------------------------------------
            await self._run_documentation_phase()

            # Mark root task complete
            self.root_task.status = TaskStatus.COMPLETED
            self.root_task.current_agent = None
            self.root_task.completed_at = datetime.utcnow()
            await self.session.commit()

            logger.info(
                "dag_execution_complete",
                root_task_id=str(self.root_task.id),
                tasks_completed=self._tasks_completed,
                loop_iterations=self._loop_iterations,
            )

            return ExecutionResult(
                success=True,
                tasks_completed=self._tasks_completed,
            )

        except Exception as e:
            logger.exception(
                "dag_execution_error",
                root_task_id=str(self.root_task.id),
                error=str(e),
            )
            return ExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                tasks_completed=self._tasks_completed,
            )

    # =========================================================================
    # Signal Handling
    # =========================================================================

    def _is_timed_out(self) -> bool:
        """Check if execution has exceeded timeout."""
        elapsed = (datetime.now(UTC) - self._start_time).total_seconds()
        return elapsed > self.TIMEOUT_SECONDS

    async def _check_signals(self) -> str:
        """
        Check for external signals (pause, terminate).

        Returns:
            "CONTINUE", "PAUSED", or "TERMINATED"
        """
        try:
            await self.session.refresh(self.root_task)
        except Exception as e:
            # If refresh fails (e.g. ObjectDeletedError), assume task is gone
            logger.warning(
                "dag_executor_refresh_failed_terminating",
                root_task_id=str(self.root_task.id),
                error=str(e),
            )
            return "TERMINATED"

        if self.root_task.status == TaskStatus.PAUSED:
            return "PAUSED"

        # Check for explicit termination states
        if self.root_task.status in [
            TaskStatus.FAILED,
            TaskStatus.COMPLETED,
        ]:
            return "TERMINATED"

        # Check for "ARCHIVED" or "DELETED" status if they exist
        status_value = (
            self.root_task.status.value
            if hasattr(self.root_task.status, "value")
            else str(self.root_task.status)
        )
        if status_value.upper() in ["ARCHIVED", "DELETED", "CANCELLED"]:
            return "TERMINATED"

        return "CONTINUE"

    async def _wait_for_resume(self) -> None:
        """Block until task is resumed (exits PAUSED state)."""
        logger.info("dag_executor_pausing", root_task_id=str(self.root_task.id))

        while True:
            await asyncio.sleep(self.PAUSE_CHECK_INTERVAL)
            try:
                await self.session.refresh(self.root_task)
                if self.root_task.status != TaskStatus.PAUSED:
                    break
            except Exception:
                # If task is deleted while paused, stop waiting
                break

        logger.info("dag_executor_resumed", root_task_id=str(self.root_task.id))

    async def _all_tasks_complete(self) -> bool:
        """Check if all subtasks are complete."""
        stmt = select(func.count()).where(
            Task.parent_task_id == self.root_task.id, Task.status != TaskStatus.COMPLETED
        )
        count = (await self.session.execute(stmt)).scalar()
        return count == 0

    # =========================================================================
    # Task Execution & Validation
    # =========================================================================

    async def _execute_and_validate(self, task: Task) -> TaskExecutionResult:
        """
        Execute a single task and validate with Referee.

        Args:
            task: The task to execute

        Returns:
            TaskExecutionResult with success status
        """
        from backend.app.workers.task_executor import TaskExecutor

        # Find step_order from the root task's plan
        step_order = 1  # Default to 1 if not found
        if self.root_task.task_plan:
            plan_steps = self.root_task.task_plan.get("steps", [])
            for step in plan_steps:
                step_id = step.get("step_id") or f"step_{step.get('order')}"
                if step_id == task.title:
                    step_order = step.get("order", 1)
                    break

        # Create executor for this specific task with step_order in context
        task_context = {
            **self.context,
            "step_order": step_order,
            "root_task_id": self.root_task.id,  # For SSE streaming to root task channel
        }
        executor = TaskExecutor(
            session=self.session,
            task=task,
            context=task_context,
            max_fix_attempts=self.MAX_RETRIES,
        )

        # Execute the task
        result = await executor.execute()

        # Check if review is required
        if task.status in [TaskStatus.REVIEW_REQUIRED, TaskStatus.PLAN_REVIEW]:
            return TaskExecutionResult(success=True, requires_review=True)

        if not result.success:
            return TaskExecutionResult(success=False, error=result.error)

        # ---------------------------------------------------------
        # Referee Validation
        # ---------------------------------------------------------
        if task.definition_of_done:
            is_valid, validation_msg = self.referee.validate_contract(task.definition_of_done)

            if not is_valid:
                logger.warning(
                    "referee_rejected",
                    task_id=str(task.id),
                    reason=validation_msg,
                )

                # Check retry limit
                if task.retry_count >= self.MAX_RETRIES:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Referee rejection limit reached: {validation_msg}"
                    await self.session.commit()
                    return TaskExecutionResult(
                        success=False,
                        error=f"Task failed Referee check {self.MAX_RETRIES} times.",
                    )

                # Inject feedback and retry
                task.status = TaskStatus.PENDING
                task.retry_count += 1
                feedback = (
                    f"\n\n[SYSTEM FEEDBACK]: Previous attempt rejected. Reason: {validation_msg}"
                )
                if feedback not in task.user_request:
                    task.user_request += feedback
                await self.session.commit()

                logger.info(
                    "task_reset_for_retry",
                    task_id=str(task.id),
                    attempt=task.retry_count,
                )

                # Return success=True so the loop continues
                # The task is back to PENDING and will be picked up again
                return TaskExecutionResult(success=True)

        # ---------------------------------------------------------
        # REALITY CHECK: Verify files actually exist before COMPLETED
        # ---------------------------------------------------------
        import os

        files_affected = task.task_plan.get("files_affected", []) if task.task_plan else []
        repo_path = self.context.get("repo_path", ".")

        missing_files = []
        for file_path in files_affected:
            # Robus Regex Cleaning (Matches CoderAgent logic)
            # Remove [NEW], [MODIFY], [DELETE] prefix and quotes
            import re

            clean_path = re.sub(r"^\[.*?\]\s*", "", file_path, flags=re.IGNORECASE)
            clean_path = clean_path.strip().strip('"').strip("'")

            # Build full path
            if os.path.isabs(clean_path):
                full_path = clean_path
            else:
                full_path = os.path.join(repo_path, clean_path)

            if not os.path.exists(full_path):
                missing_files.append(clean_path)

        if missing_files:
            # CRITICAL: Files are missing - do NOT mark as complete!
            logger.error(
                "task_completion_blocked_missing_files",
                task_id=str(task.id),
                title=task.title,
                missing_files=missing_files,
                files_affected=files_affected,
            )
            task.status = TaskStatus.FAILED
            task.error_message = f"Files not created: {', '.join(missing_files)}"
            await self.session.commit()
            return TaskExecutionResult(
                success=False,
                error=f"Task failed: Expected files not found on disk: {missing_files}",
            )

        # Mark task complete ONLY if files verified
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        await self.session.commit()

        logger.info(
            "task_completed_verified",
            task_id=str(task.id),
            title=task.title,
            files_verified=files_affected,
        )

        return TaskExecutionResult(success=True, changeset=result.changeset)

    # =========================================================================
    # Documentation Phase
    # =========================================================================

    async def _run_documentation_phase(self) -> None:
        """Run documentation phase after all tasks complete."""
        from gravity_core.agents.docs import DocsAgent
        from gravity_core.llm import LLMClient

        from backend.app.config import settings

        self.root_task.status = TaskStatus.DOCUMENTING
        self.root_task.current_agent = "docs"
        await self.session.commit()

        try:
            llm_client = LLMClient(
                openai_api_key=settings.openai_api_key,
                gemini_api_key=settings.google_api_key,
                enable_fallback=True,
                max_retries=3,
            )

            docs = DocsAgent(
                llm_client=llm_client,
                model_name=settings.default_llm_model,
            )

            docs_context = {
                **self.context,
                "changes": [],  # TODO: Aggregate changes from subtasks
                "plan_summary": self.root_task.task_plan.get("summary", "")
                if self.root_task.task_plan
                else "",
            }

            docs_output = await docs.execute(self.root_task.id, docs_context)

            # Log the documentation output
            from backend.app.workers.agent_runner import log_agent_output

            await log_agent_output(
                session=self.session,
                task_id=self.root_task.id,
                agent_output=docs_output,
                step_number=self.root_task.current_step or 0,
            )

            logger.info(
                "documentation_phase_complete",
                task_id=str(self.root_task.id),
            )

        except Exception as e:
            logger.warning(
                "documentation_phase_failed",
                task_id=str(self.root_task.id),
                error=str(e),
            )
            # Documentation failure is not fatal
