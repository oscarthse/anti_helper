"""
QA Agent - The Automated Debugger

Executes tests in the sandbox, interprets failures using LLM,
and generates structured fix instructions for the Coder Agent.

Key Responsibilities:
1. Run test commands in isolated Docker sandbox
2. Diagnose failures from stdout/stderr using LLM
3. Generate precise fix Tool Calls for automated self-healing
4. Complete the Code → Test → Fix loop
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog

from gravity_core.base import BaseAgent
from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    ExecutionRun,
    ToolCall,
)
from gravity_core.llm import LLMClient, LLMClientError, LLMValidationError

logger = structlog.get_logger(__name__)


# =============================================================================
# System Prompt (Debugging Specialist Persona)
# =============================================================================


QA_SYSTEM_PROMPT = """You are a **Senior Debugging Specialist** - the final quality gate before code ships.

## Your Persona
You think like Kent Beck debugging a test failure - methodical, precise, and minimal.
You don't just find problems, you prescribe the exact fix.

## Your Mission
Analyze test failures and generate the MOST PRECISE, ATOMIC fix possible.
Your fix will be automatically applied by the Coder Agent - there is no human in the loop.

## Your Input Sources
1. **Primary**: Raw stdout/stderr from the test execution
2. **Secondary**: The ChangeSet (code the Coder just wrote)
3. **Context**: The TaskPlan step that led to the failure

## Your Output Rules
1. **If tests pass**: Report success, no fix needed
2. **If tests fail**: You MUST output a `suggested_fix` ToolCall

## CRITICAL CONSTRAINTS
- You can ONLY run commands via `run_shell_command` tool
- You CANNOT directly edit files - only suggest edits
- Your fix must be a SINGLE, ATOMIC change
- Focus on the ROOT CAUSE, not symptoms

## Diagnosis Process
1. Parse the error traceback to identify the failing file and line
2. Identify the error type (ImportError, AssertionError, TypeError, etc.)
3. Correlate with the recent ChangeSet to find the cause
4. Generate the minimal fix as a tool call

## Fix Format
Your `suggested_fix` must be a structured tool call:
{
    "tool_name": "edit_file_snippet",
    "arguments": {
        "file_path": "path/to/file.py",
        "original_code": "the exact broken code",
        "new_code": "the fixed code",
        "explanation": "Why this fixes the issue"
    }
}"""


# Tool for generating fixes (internal schema)
FIX_TOOL = {
    "name": "suggest_fix",
    "description": "Suggest a code fix for the Coder Agent to apply. Use this when tests fail.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file that needs fixing",
            },
            "original_code": {
                "type": "string",
                "description": "The exact code that is broken",
            },
            "new_code": {
                "type": "string",
                "description": "The fixed code to replace it with",
            },
            "explanation": {
                "type": "string",
                "description": "Clear explanation of why this fixes the issue",
            },
            "error_type": {
                "type": "string",
                "description": "Category of error (ImportError, TypeError, AssertionError, etc.)",
            },
        },
        "required": ["file_path", "original_code", "new_code", "explanation"],
    },
}


# =============================================================================
# QAAgent Implementation
# =============================================================================


class QAAgent(BaseAgent):
    """
    The QA Agent - Automated Debugger persona.

    Executes tests, diagnoses failures via LLM, and generates
    structured fix instructions for the Code→Test→Fix loop.
    """

    persona = AgentPersona.QA
    system_prompt = QA_SYSTEM_PROMPT
    available_tools = [
        # Runtime tools (execution only, no file manipulation)
        "run_shell_command",
        "read_sandbox_logs",
        # Perception for debugging
        "search_codebase",
        "get_file_signatures",
    ]

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model_name: str = "gpt-4o",
        max_fix_attempts: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        Initialize QA Agent.

        Args:
            llm_client: LLMClient instance (created if not provided)
            model_name: LLM model to use
            max_fix_attempts: Maximum auto-fix attempts before giving up
        """
        super().__init__(**kwargs)

        self.model_name = model_name
        self.llm_client = llm_client or LLMClient()
        self.max_fix_attempts = max_fix_attempts
        self._execution_runs: list[ExecutionRun] = []
        self._suggested_fix: Optional[ToolCall] = None

        logger.info(
            "qa_initialized",
            model=model_name,
            max_fix_attempts=max_fix_attempts,
        )

    async def execute(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """
        Run tests and diagnose any failures.

        Args:
            task_id: The task being tested
            context: Should contain:
                - test_commands: List of commands to run
                - repo_path: Path to repository
                - last_changeset: The code that was just written (optional)
                - plan_step: The step that led to this (optional)

        Returns:
            AgentOutput with ExecutionRun details and optional fix suggestion
        """
        test_commands = context.get("test_commands", ["pytest"])
        repo_path = context.get("repo_path", ".")
        last_changeset = context.get("last_changeset", {})
        plan_step = context.get("plan_step", {})

        logger.info(
            "qa_starting",
            task_id=str(task_id),
            commands=test_commands,
        )

        self._execution_runs = []
        self._suggested_fix = None

        try:
            # =================================================================
            # Phase 1: EXECUTION - Run all test commands
            # =================================================================

            all_passed = True
            failed_run: Optional[ExecutionRun] = None

            for command in test_commands:
                run = await self._execute_test(command, repo_path)
                self._execution_runs.append(run)

                if not run.success:
                    all_passed = False
                    failed_run = run
                    break  # Stop on first failure to diagnose

            # =================================================================
            # Phase 2: DIAGNOSIS or SUCCESS
            # =================================================================

            if all_passed:
                return self._build_success_output()

            # Tests failed - diagnose and generate fix
            assert failed_run is not None

            fix = await self._diagnose_and_generate_fix(
                failed_run=failed_run,
                last_changeset=last_changeset,
                plan_step=plan_step,
            )

            if fix:
                self._suggested_fix = fix
                return self._build_failure_with_fix_output(failed_run, fix)
            else:
                return self._build_failure_no_fix_output(failed_run)

        except LLMClientError as e:
            logger.error(
                "qa_llm_error",
                task_id=str(task_id),
                error=str(e),
            )
            return self.build_output(
                ui_title="⚠️ Diagnosis Failed",
                ui_subtitle="Unable to analyze test failure due to an API error.",
                technical_reasoning=json.dumps({"error": str(e)}, indent=2),
                confidence_score=0.0,
            )

    async def _execute_test(
        self,
        command: str,
        repo_path: str,
    ) -> ExecutionRun:
        """Execute a test command in the sandbox."""
        logger.info("qa_executing_test", command=command)

        result = await self.call_tool(
            "run_shell_command",
            command=command,
            working_directory=repo_path,
            timeout_seconds=300,  # 5 minute timeout
        )

        # Parse the tool result into ExecutionRun
        stdout = ""
        stderr = ""
        exit_code = 1
        duration_ms = 0

        if result.success and result.result:
            # Parse the result (format depends on tool implementation)
            if isinstance(result.result, dict):
                stdout = result.result.get("stdout", "")
                stderr = result.result.get("stderr", "")
                exit_code = result.result.get("exit_code", 0)
                duration_ms = result.result.get("duration_ms", 0)
            else:
                stdout = str(result.result)
                exit_code = 0
        elif result.error:
            stderr = result.error
            exit_code = 1

        return ExecutionRun(
            command=command,
            working_directory=repo_path,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )

    async def _diagnose_and_generate_fix(
        self,
        failed_run: ExecutionRun,
        last_changeset: dict,
        plan_step: dict,
    ) -> Optional[ToolCall]:
        """
        Use LLM to diagnose failure and generate a fix.

        Returns:
            ToolCall with fix suggestion, or None if unable to diagnose
        """
        logger.info(
            "qa_diagnosing_failure",
            command=failed_run.command,
            exit_code=failed_run.exit_code,
        )

        # Build the diagnosis prompt
        prompt = self._build_diagnosis_prompt(
            failed_run=failed_run,
            last_changeset=last_changeset,
            plan_step=plan_step,
        )

        # Use LLM with tool-calling to force structured fix output
        response = await self.llm_client.generate_with_tools(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT,
            tools=[FIX_TOOL],
            model=self.model_name,
            tool_choice="auto",  # Let LLM decide if fix is possible
        )

        # Extract fix from tool calls
        tool_calls = response.get("tool_calls", [])

        for tc in tool_calls:
            if tc.get("name") == "suggest_fix":
                args = tc.get("arguments", {})
                return ToolCall(
                    tool_name="edit_file_snippet",
                    arguments={
                        "file_path": args.get("file_path", ""),
                        "original_code": args.get("original_code", ""),
                        "new_code": args.get("new_code", ""),
                        "explanation": args.get("explanation", ""),
                    },
                    result=None,
                    success=True,
                    duration_ms=0,
                )

        # LLM didn't suggest a fix (maybe couldn't diagnose)
        logger.warning("qa_no_fix_generated", command=failed_run.command)
        return None

    def _build_diagnosis_prompt(
        self,
        failed_run: ExecutionRun,
        last_changeset: dict,
        plan_step: dict,
    ) -> str:
        """Build the prompt for LLM diagnosis."""
        changeset_context = ""
        if last_changeset:
            changeset_context = f"""
## Recent Code Changes (ChangeSet)
File: {last_changeset.get('file_path', 'unknown')}
Action: {last_changeset.get('action', 'modify')}

```diff
{last_changeset.get('diff', 'No diff available')[:2000]}
```
"""

        step_context = ""
        if plan_step:
            step_context = f"""
## TaskPlan Step
{plan_step.get('description', 'No description')}
"""

        return f"""## Test Failure Analysis

### Command Executed
```
{failed_run.command}
```

### Exit Code
{failed_run.exit_code}

### Standard Output
```
{failed_run.stdout[:3000] if failed_run.stdout else '(empty)'}
```

### Standard Error (Traceback)
```
{failed_run.stderr[:3000] if failed_run.stderr else '(empty)'}
```

{changeset_context}
{step_context}

## Your Task
1. Identify the ROOT CAUSE of this failure
2. If you can fix it, call the `suggest_fix` tool with the precise change
3. The fix should be MINIMAL and ATOMIC

Focus on the actual error, not workarounds."""

    def _build_success_output(self) -> AgentOutput:
        """Build output when all tests pass."""
        total = len(self._execution_runs)

        return self.build_output(
            ui_title="✅ All Tests Passed",
            ui_subtitle=f"All {total} test command(s) passed. The changes work as expected.",
            technical_reasoning=json.dumps({
                "status": "success",
                "runs": [
                    {
                        "command": run.command,
                        "exit_code": run.exit_code,
                        "duration_ms": run.duration_ms,
                    }
                    for run in self._execution_runs
                ],
            }, indent=2),
            confidence_score=0.95,
        )

    def _build_failure_with_fix_output(
        self,
        failed_run: ExecutionRun,
        fix: ToolCall,
    ) -> AgentOutput:
        """Build output when tests fail but fix is suggested."""
        return self.build_output(
            ui_title="❌ Tests Failed → Fix Suggested",
            ui_subtitle=f"Test `{failed_run.command}` failed. I've diagnosed the issue and generated a fix.",
            technical_reasoning=json.dumps({
                "status": "failed_with_fix",
                "failed_command": failed_run.command,
                "exit_code": failed_run.exit_code,
                "error_summary": self._extract_error_summary(failed_run),
                "suggested_fix": {
                    "tool_name": fix.tool_name,
                    "arguments": fix.arguments,
                },
            }, indent=2),
            confidence_score=0.6,  # Moderate confidence (fix needs verification)
            tool_calls=[fix],  # Include the fix as a tool call
        )

    def _build_failure_no_fix_output(
        self,
        failed_run: ExecutionRun,
    ) -> AgentOutput:
        """Build output when tests fail and no fix could be generated."""
        return self.build_output(
            ui_title="❌ Tests Failed → Manual Review Needed",
            ui_subtitle=f"Test `{failed_run.command}` failed. Unable to automatically diagnose the root cause.",
            technical_reasoning=json.dumps({
                "status": "failed_no_fix",
                "failed_command": failed_run.command,
                "exit_code": failed_run.exit_code,
                "stdout": failed_run.stdout[:2000] if failed_run.stdout else "",
                "stderr": failed_run.stderr[:2000] if failed_run.stderr else "",
                "error_summary": self._extract_error_summary(failed_run),
            }, indent=2),
            confidence_score=0.2,  # Low confidence - needs human review
        )

    def _extract_error_summary(self, run: ExecutionRun) -> str:
        """Extract a brief error summary from output."""
        output = run.stderr or run.stdout or ""

        # Look for common error patterns
        lines = output.split("\n")

        # Find the first line with "Error" or "Exception"
        for line in reversed(lines):
            if any(kw in line for kw in ["Error:", "Exception:", "FAILED", "AssertionError"]):
                return line.strip()[:200]

        # Fallback to last non-empty line
        for line in reversed(lines):
            if line.strip():
                return line.strip()[:200]

        return "Unknown error"

    def has_suggested_fix(self) -> bool:
        """Check if the last execution produced a fix suggestion."""
        return self._suggested_fix is not None

    def get_suggested_fix(self) -> Optional[ToolCall]:
        """Get the suggested fix from the last execution."""
        return self._suggested_fix
