"""
Task Executor - Single Task Execution with Reality Engine

This module handles the execution of a single atomic task (Code → Test → Fix).
It includes the "Reality Engine" - mandatory file write verification to prevent
the agent from hallucinating success without actually writing files.

The Reality Engine Protocol:
1. WRITE: Actually write files to disk
2. VERIFY: Check that files exist with os.path.exists()
3. LOG: Explicitly state "I have physically written X to disk"
4. FAIL: If verification fails, raise an error immediately
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.models import Task, TaskStatus
from backend.app.schemas.reality import FileAction, VerifiedFileAction
from libs.gravity_core.tracking import (
    ExecutionMetrics,
    _metrics_context,
    get_current_metrics,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class ExecutionResult:
    """Result of task execution."""

    success: bool
    error: str | None = None
    changeset: dict = field(default_factory=dict)
    files_written: list[str] = field(default_factory=list)


class RealityCheckError(Exception):
    """Raised when file write verification fails."""

    def __init__(self, missing_files: list[str]):
        self.missing_files = missing_files
        super().__init__(
            f"Reality Check Failed: Agent claimed to create files, but they are "
            f"missing from disk: {', '.join(missing_files)}"
        )


# =============================================================================
# Reality Engine - File Write Enforcement
# =============================================================================


class RealityEngine:
    """
    The Reality Engine ensures agents actually write files to disk.

    Problem: LLMs can "hallucinate" tool calls - claiming to write files
    without actually doing so. This causes silent failures where the agent
    reports success but no code was written.

    Solution: Every file operation is verified using Pydantic validators.
    The VerifiedFileAction model validates:
    1. File exists on disk
    2. File is not empty (0 bytes)
    3. Python files have real implementations (not just 'pass')
    """

    def __init__(self, repo_path: str, step_index: int = 0):
        self.repo_path = Path(repo_path)
        self.step_index = step_index
        self._written_files: list[str] = []
        self._verified_actions: list[VerifiedFileAction] = []

    def write_file(self, relative_path: str, content: str) -> VerifiedFileAction:
        """
        Write a file to disk with verification.

        Args:
            relative_path: Path relative to repo root
            content: File content to write

        Returns:
            VerifiedFileAction - validated proof the file was written

        Raises:
            ValueError: If file fails validation (not written, empty, or lazy code)
            RealityCheckError: If file was not written successfully
        """
        # Normalize path
        if Path(relative_path).is_absolute():
            absolute_path = Path(relative_path)
        else:
            absolute_path = self.repo_path / relative_path

        # Create parent directories
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        absolute_path.write_text(content, encoding="utf-8")

        # Verify content was written correctly (basic check before Pydantic)
        written_content = absolute_path.read_text(encoding="utf-8")
        if written_content != content:
            logger.error(
                "reality_check_content_mismatch",
                path=str(absolute_path),
                expected_len=len(content),
                actual_len=len(written_content),
            )
            raise RealityCheckError([str(absolute_path)])

        # PYDANTIC VALIDATION: Create verified action (will raise on failure)
        try:
            verified_action = VerifiedFileAction(
                path=str(absolute_path),
                action=FileAction.CREATE,
                byte_size=len(content),  # Will be updated by validator
                step_index=self.step_index,
            )
        except ValueError as e:
            # Quality validation failed - log and re-raise
            logger.error(
                "reality_engine_validation_failed",
                path=str(absolute_path),
                error=str(e),
            )
            raise

        self._written_files.append(str(absolute_path))
        self._verified_actions.append(verified_action)

        logger.info(
            "reality_engine_file_verified",
            path=str(absolute_path),
            size_bytes=verified_action.byte_size,
            step_index=self.step_index,
            quality_checks=verified_action.quality_checks_passed,
            quality_warnings=verified_action.quality_warnings,
            message=f"VERIFIED: '{relative_path}' written and validated.",
        )

        return verified_action

    def edit_file(
        self,
        relative_path: str,
        original_content: str,
        new_content: str,
        occurrence: int = 1,
    ) -> VerifiedFileAction:
        """
        Edit a file on disk with verification.

        Args:
            relative_path: Path relative to repo root
            original_content: Content to replace
            new_content: Replacement content
            occurrence: Which occurrence to replace (1-indexed, 0 = all)

        Returns:
            VerifiedFileAction - validated proof the file was edited

        Raises:
            ValueError: If file fails validation
            RealityCheckError: If edit was not applied successfully
        """
        # Normalize path
        if Path(relative_path).is_absolute():
            absolute_path = Path(relative_path)
        else:
            absolute_path = self.repo_path / relative_path

        # Read current content
        if not absolute_path.exists():
            raise FileNotFoundError(f"Cannot edit non-existent file: {absolute_path}")

        current_content = absolute_path.read_text(encoding="utf-8")

        # Verify original content exists
        if original_content not in current_content:
            raise ValueError(
                f"Original content not found in file. " f"Cannot perform edit on {absolute_path}"
            )

        # Perform replacement
        if occurrence == 0:
            # Replace all occurrences
            modified_content = current_content.replace(original_content, new_content)
        else:
            # Replace specific occurrence
            idx = -1
            for _ in range(occurrence):
                idx = current_content.find(original_content, idx + 1)
                if idx == -1:
                    raise ValueError(f"Could not find occurrence {occurrence} of original content")

            modified_content = (
                current_content[:idx] + new_content + current_content[idx + len(original_content) :]
            )

        # Write modified content
        absolute_path.write_text(modified_content, encoding="utf-8")

        # REALITY CHECK: Verify edit was applied
        verified_content = absolute_path.read_text(encoding="utf-8")
        if new_content not in verified_content:
            raise RealityCheckError([str(absolute_path)])

        # PYDANTIC VALIDATION: Create verified action
        try:
            verified_action = VerifiedFileAction(
                path=str(absolute_path),
                action=FileAction.UPDATE,
                byte_size=len(modified_content),
                step_index=self.step_index,
            )
        except ValueError as e:
            logger.error(
                "reality_engine_edit_validation_failed",
                path=str(absolute_path),
                error=str(e),
            )
            raise

        self._written_files.append(str(absolute_path))
        self._verified_actions.append(verified_action)

        logger.info(
            "reality_engine_file_edited_verified",
            path=str(absolute_path),
            old_len=len(original_content),
            new_len=len(new_content),
            step_index=self.step_index,
            quality_checks=verified_action.quality_checks_passed,
            message=f"VERIFIED: '{relative_path}' edited and validated.",
        )

        return verified_action

    def verify_all_writes(self, expected_files: list[str]) -> tuple[bool, list[str]]:
        """
        Verify all expected files were written.

        Args:
            expected_files: List of file paths that should exist

        Returns:
            Tuple of (all_verified, missing_files)
        """
        missing = []
        for file_path in expected_files:
            # Normalize path
            if Path(file_path).is_absolute():
                check_path = Path(file_path)
            else:
                check_path = self.repo_path / file_path

            if not check_path.exists():
                missing.append(str(check_path))
                logger.error(
                    "reality_check_missing_file",
                    path=str(check_path),
                )

        return len(missing) == 0, missing

    @property
    def written_files(self) -> list[str]:
        """Get list of files written during this session."""
        return self._written_files.copy()

    @property
    def verified_actions(self) -> list[VerifiedFileAction]:
        """Get list of verified file actions during this session."""
        return self._verified_actions.copy()


# =============================================================================
# Task Executor
# =============================================================================


class TaskExecutor:
    """
    Executes a single atomic task (Code → Test → Fix loop).

    Uses the Reality Engine to ensure all file operations are verified.
    """

    def __init__(
        self,
        session: AsyncSession,
        task: Task,
        context: dict[str, Any],
        max_fix_attempts: int = 3,
    ):
        self.session = session
        self.task = task
        self.context = context
        self.max_fix_attempts = max_fix_attempts

        repo_path = context.get("repo_path", ".")
        step_index = context.get("step_order", 0)  # 0-indexed for UI
        self.reality_engine = RealityEngine(repo_path, step_index=step_index)

        self._changeset: dict = {}

    async def execute(self) -> ExecutionResult:
        """
        Execute the task with Code → Test → Fix loop.

        Returns:
            ExecutionResult with success status and changeset
        """
        from gravity_core.agents.coder import CoderAgent
        from gravity_core.agents.qa import QAAgent
        from gravity_core.llm import LLMClient

        # NEW: Import Policy Manager explicitly
        from gravity_core.tools.policies import (
            FileAccessPolicy,
            clear_current_policy,
            set_current_policy,
        )

        logger.info(
            "task_executor_started",
            task_id=str(self.task.id),
            title=self.task.title,
        )

        # Initialize LLM client
        llm_client = LLMClient(
            openai_api_key=settings.openai_api_key,
            gemini_api_key=settings.google_api_key,
            enable_fallback=True,
            max_retries=3,
        )

        self.task.status = TaskStatus.EXECUTING
        await self.session.commit()

        # ---------------------------------------------------------
        # POLICY SETUP: Enforce Read-Before-Write & Metrics
        # ---------------------------------------------------------
        policy = FileAccessPolicy()
        set_current_policy(policy)
        metrics_token = _metrics_context.set(ExecutionMetrics())

        try:
            fix_attempts = 0
            test_commands = self.context.get("test_commands", ["pytest"])

            while fix_attempts < self.max_fix_attempts:
                # ---------------------------------------------------------
                # CODER Phase: Generate/Edit Code
                # ---------------------------------------------------------
                self.task.current_agent = "coder_be"
                await self.session.commit()

                coder = CoderAgent(
                    specialty="be",
                    llm_client=llm_client,
                    # Removed model_name override to use role-based config
                )

                # Get step metadata from subtask's task_plan (populated by _materialize_plan_to_db)
                step_metadata = self.task.task_plan or {}
                files_affected = step_metadata.get("files_affected", [])

                # DIAGNOSTIC: Log what files we're expecting this subtask to create
                logger.info(
                    "subtask_files_affected",
                    task_id=str(self.task.id),
                    task_title=self.task.title,
                    step_order=self.context.get("step_order", 0),
                    files_affected=files_affected,
                    step_metadata_keys=list(step_metadata.keys()),
                )

                step_context = {
                    **self.context,
                    "step": {
                        "description": self.task.user_request,
                        "files_affected": files_affected,
                    },
                    "task_description": self.task.user_request,
                    "reality_engine": self.reality_engine,  # Pass Reality Engine
                }

                coder_output = await coder.execute(self.task.id, step_context)

                # Log coder output
                from backend.app.workers.agent_runner import log_agent_output

                await log_agent_output(
                    session=self.session,
                    task_id=self.task.id,
                    agent_output=coder_output,
                    step_number=self.context.get("step_order", 1),
                    root_task_id=self.context.get("root_task_id"),
                )

                # ---------------------------------------------------------
                # REALITY CHECK: Verify files were written
                # ---------------------------------------------------------
                claimed_files = self._extract_claimed_files(coder_output)

                if claimed_files:
                    all_verified, missing = self.reality_engine.verify_all_writes(claimed_files)

                    if not all_verified:
                        fix_attempts += 1

                        # Inject error feedback
                        step_context["system_feedback"] = (
                            f"CRITICAL ERROR: You claimed to create file(s) {missing}, "
                            f"but I checked the OS and they are MISSING. You likely "
                            f"hallucinated the tool call or the path is wrong. "
                            f"TRY AGAIN. USE THE TOOLS."
                        )

                        logger.warning(
                            "reality_check_failed",
                            task_id=str(self.task.id),
                            missing_files=missing,
                            attempt=fix_attempts,
                        )
                        continue

                # ---------------------------------------------------------
                # PUBLISH VERIFIED FILE EVENTS
                # Only reached if reality check passed - files are real
                # ---------------------------------------------------------
                from backend.app.workers.agent_runner import publish_verified_file_event

                for verified_action in self.reality_engine.verified_actions:
                    await publish_verified_file_event(
                        task_id=self.task.id,
                        verified_action=verified_action,
                        root_task_id=self.context.get("root_task_id"),
                    )

                # Check if review required
                if coder_output.requires_review:
                    self.task.status = TaskStatus.REVIEW_REQUIRED
                    await self.session.commit()
                    return ExecutionResult(success=True)

                # Track changeset
                try:
                    reasoning = json.loads(coder_output.technical_reasoning)
                    changes = reasoning.get("changes", [])
                    if changes:
                        self._changeset = changes[0]
                except (json.JSONDecodeError, KeyError):
                    pass

                await self.session.commit()

                # ---------------------------------------------------------
                # QA Phase: Run Tests
                # ---------------------------------------------------------
                self.task.current_agent = "qa"
                self.task.status = TaskStatus.TESTING
                await self.session.commit()

                qa = QAAgent(
                    llm_client=llm_client,
                    # Removed model_name override to use role-based config
                    max_fix_attempts=self.max_fix_attempts,
                )

                qa_context = {
                    **self.context,
                    "test_commands": test_commands,
                    "last_changeset": self._changeset,
                    "task_goal": self.task.user_request,
                }

                qa_output = await qa.execute(self.task.id, qa_context)

                # METRICS: Capture QA metrics
                if hasattr(qa, "_execution_runs") and qa._execution_runs:
                    last_run = qa._execution_runs[-1]
                    self.task.tests_run_command = last_run.get("command")
                    self.task.tests_exit_code = last_run.get("exit_code")

                await self.session.commit()

                from backend.app.workers.agent_runner import log_agent_output

                await log_agent_output(
                    session=self.session,
                    task_id=self.task.id,
                    agent_output=qa_output,
                    step_number=self.context.get("step_order", 1),
                    root_task_id=self.context.get("root_task_id"),
                )

                # Check test results
                if qa_output.confidence_score >= 0.9:
                    # Tests passed
                    logger.info("tests_passed", task_id=str(self.task.id))
                    break

                # Tests failed
                if qa.has_suggested_fix():
                    fix_attempts += 1
                    self.task.fix_attempts_count = fix_attempts  # Update counter

                    suggested_fix = qa.get_suggested_fix()

                    logger.info(
                        "applying_suggested_fix",
                        task_id=str(self.task.id),
                        attempt=fix_attempts,
                    )

                    step_context["suggested_fix"] = {
                        "tool_call": suggested_fix.model_dump() if suggested_fix else None,
                        "attempt": fix_attempts,
                    }
                    continue
                else:
                    if qa_output.confidence_score < 0.5:
                        return ExecutionResult(
                            success=False,
                            error="Tests failed without automatic fix",
                        )
                    break

            if fix_attempts >= self.max_fix_attempts:
                logger.warning(
                    "max_fix_attempts_reached",
                    task_id=str(self.task.id),
                )

            # METRICS: Capture quality metrics
            metrics = get_current_metrics()
            self.task.files_changed_count = len(metrics.files_changed)
            # self.task.fix_attempts_count = metrics.fix_attempts # Need to instrument fix attempts first

            # Merge RealityEngine manual writes if any (legacy support)
            if hasattr(self.reality_engine, "written_files"):
                manual_writes = set(self.reality_engine.written_files)
                # Combine with tracked writes
                total_files = len(manual_writes.union(metrics.files_changed))
                self.task.files_changed_count = total_files

            await self.session.commit()

            return ExecutionResult(
                success=True,
                changeset=self._changeset,
                files_written=list(metrics.files_changed),
            )
        finally:
            # CLEANUP: Ensure policy and metrics are cleared
            clear_current_policy()
            _metrics_context.reset(metrics_token)

    def _extract_claimed_files(self, coder_output) -> list[str]:
        """Extract file paths that the coder claimed to create/edit."""
        files = []

        if coder_output.tool_calls:
            for tool in coder_output.tool_calls:
                if tool.tool_name in ["create_new_module", "edit_file_snippet", "write_to_file"]:
                    path = (
                        tool.arguments.get("file_path")
                        or tool.arguments.get("path")
                        or tool.arguments.get("target_file")
                    )
                    if path:
                        files.append(path)

        return files
