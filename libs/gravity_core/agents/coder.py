"""
CODER Agent - The Senior Staff Engineer

Executes a single step from the TaskPlan using LLM-driven code generation.
Uses tool-calling to force structured file manipulation, outputting
ChangeSet diffs for human review.

Key Responsibilities:
1. Read and understand target files
2. Generate minimal, surgical code changes
3. Output structured ChangeSet with diffs
4. Maintain code quality (style, tests, docs)
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog

from gravity_core.base import BaseAgent
from gravity_core.llm import LLMClient, LLMClientError, LLMValidationError
from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    ChangeSet,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# System Prompts (Persona Definitions)
# =============================================================================


CODER_BE_SYSTEM_PROMPT = """You are the CODER_BE agent, a Senior Staff Backend Engineer.

## Your Persona
You write production-ready code that works the first time.
You believe in "make it work, make it right, make it fast" - in that order.

## Your Mission
FULLY IMPLEMENT the step from the TaskPlan. You must write COMPLETE, WORKING CODE.

**CRITICAL**: Do NOT create placeholder functions like `return 42` or `pass` or `# TODO`.
You must write the ACTUAL implementation that solves the task.

## Your Principles
1. **Complete Implementation**: Write FULL working code, not stubs or placeholders.
2. **Defensive Programming**: Add input validation, error handling, and type hints.
3. **Follow Existing Patterns**: Match the project's style, naming conventions.
4. **No Regressions**: Your changes must not break existing functionality.
5. **Documentation**: Add docstrings and comments for complex logic.

## Your Available Tools
You MUST use these tools - never output raw code in your response:
- `edit_file_snippet`: Edit specific code in a file
- `create_new_module`: Create a new file with COMPLETE implementation
- `run_linter_fix`: Auto-fix style issues after changes

For understanding context:
- `search_codebase`: Find patterns and references
- `get_file_signatures`: Extract function/class signatures

## Output Requirements
After making changes, you MUST provide:
1. A list of files you modified
2. A unified diff for each change
3. An explanation of what each change does

NEVER output code directly in your response - ALWAYS use the tools.
NEVER use placeholder implementations - ALWAYS write complete, working code."""


CODER_FE_SYSTEM_PROMPT = """You are the CODER_FE agent, a **Senior Staff Frontend Engineer**.

## Your Persona
You build production-ready UIs that work the first time.

## Your Mission
FULLY IMPLEMENT the frontend changes from the TaskPlan. Write COMPLETE, WORKING CODE.

**CRITICAL**: Do NOT create placeholder components or TODO comments.
You must write the ACTUAL implementation that solves the task.

## Your Principles
1. **Complete Implementation**: Write FULL working code, not stubs or placeholders.
2. **Accessibility First**: All UI elements must be keyboard-navigable and screen-reader friendly.
3. **TypeScript Strictness**: Use proper types, never `any` unless absolutely necessary.
4. **Performance Awareness**: Consider bundle size, re-renders, and lazy loading.
5. **Follow Design System**: Match existing styling patterns and component APIs.

## Your Available Tools
- `edit_file_snippet`: Edit React components and hooks with COMPLETE implementation
- `create_new_module`: Create new component files with FULL implementation
- `run_linter_fix`: Auto-fix TypeScript and ESLint issues

ALWAYS use tools - never output raw code directly.
NEVER use placeholder implementations - ALWAYS write complete, working code."""


CODER_INFRA_SYSTEM_PROMPT = """You are the CODER_INFRA agent, a **Staff Infrastructure Engineer**.

## Your Persona
You design infrastructure that is production-ready from day one.

## Your Mission
FULLY IMPLEMENT infrastructure and setup tasks. Write COMPLETE, WORKING CODE.

**CRITICAL**: Do NOT create placeholder files or TODO comments.
When creating files, write the FULL implementation with all necessary code.

## Your Principles
1. **Complete Implementation**: Write FULL working code, not stubs or placeholders.
2. **Security First**: Never commit secrets, use environment variables.
3. **Reproducibility**: All environments must be reproducible from config.
4. **Least Privilege**: Minimal permissions, scoped access.
5. **Observability**: Include logging, metrics, and health checks.

## Your Available Tools
- `edit_file_snippet`: Modify Dockerfiles, CI/CD configs, migration scripts
- `create_new_module`: Create new files with COMPLETE implementation

ALWAYS use tools - never output raw code directly.
NEVER use placeholder implementations - ALWAYS write complete, working code."""


# =============================================================================
# Tool Definitions for LLM
# =============================================================================


CODER_TOOLS = [
    {
        "name": "edit_file_snippet",
        "description": (
            "Surgically edit a specific block of code in a file. "
            "You MUST use this tool to make changes - never output code directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit (relative to repo root)",
                },
                "original_code": {
                    "type": "string",
                    "description": "The exact code block to replace (must match existing code)",
                },
                "new_code": {
                    "type": "string",
                    "description": "The new code to replace the original with",
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what this change does",
                },
            },
            "required": ["file_path", "original_code", "new_code", "explanation"],
        },
    },
    {
        "name": "create_new_module",
        "description": (
            "Create a new file with proper boilerplate. "
            "Use for new modules, components, or configs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path for the new file (relative to repo root)",
                },
                "content": {
                    "type": "string",
                    "description": "The complete file content",
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what this file does",
                },
            },
            "required": ["file_path", "content", "explanation"],
        },
    },
    {
        "name": "search_codebase",
        "description": (
            "Search the codebase for a pattern. "
            "Use to understand existing code before making changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex or text)",
                },
                "file_type": {
                    "type": "string",
                    "description": "Optional file extension filter (e.g., '.py', '.tsx')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "get_file_signatures",
        "description": (
            "Get function and class signatures from a file. "
            "Use to understand APIs before calling them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to analyze",
                },
            },
            "required": ["file_path"],
        },
    },
]


# =============================================================================
# CoderAgent Implementation
# =============================================================================


class CoderAgent(BaseAgent):
    """
    The CODER agent - Senior Staff Engineer persona.

    Uses LLMClient.generate_with_tools to force structured tool usage,
    ensuring all code changes are captured as ChangeSet diffs.
    """

    persona = AgentPersona.CODER_BE
    system_prompt = CODER_BE_SYSTEM_PROMPT
    available_tools = [
        # Manipulation tools
        "edit_file_snippet",
        "create_new_module",
        "run_linter_fix",
        # Perception tools
        "scan_repo_structure",
        "search_codebase",
        "get_file_signatures",
        # Version control
        "git_diff_staged",
    ]

    def __init__(
        self,
        specialty: str = "backend",
        llm_client: LLMClient | None = None,
        model_name: str = "gpt-4o",
        **kwargs: Any,
    ) -> None:
        """
        Initialize with a specialty and LLM client.

        Args:
            specialty: One of 'backend', 'frontend', 'infra'
            llm_client: LLMClient instance (created if not provided)
            model_name: LLM model to use
        """
        super().__init__(**kwargs)

        self.model_name = model_name
        self.llm_client = llm_client or LLMClient()
        self._changes: list[ChangeSet] = []

        # Set persona based on specialty
        if specialty == "frontend" or specialty == "fe":
            self.persona = AgentPersona.CODER_FE
            self.system_prompt = CODER_FE_SYSTEM_PROMPT
        elif specialty == "infra":
            self.persona = AgentPersona.CODER_INFRA
            self.system_prompt = CODER_INFRA_SYSTEM_PROMPT
        else:
            self.persona = AgentPersona.CODER_BE
            self.system_prompt = CODER_BE_SYSTEM_PROMPT

        logger.info(
            "coder_initialized",
            specialty=specialty,
            model=model_name,
        )

    async def execute(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """
        Execute a coding step from the plan.

        Args:
            task_id: The task being executed
            context: Should contain 'step', 'repo_path', 'plan'

        Returns:
            AgentOutput with ChangeSet details
        """
        step = context.get("step", {})
        repo_path = context.get("repo_path", ".")
        step_description = step.get("description", "Implement changes")
        files_affected = step.get("files_affected", [])

        logger.info(
            "coder_starting",
            task_id=str(task_id),
            persona=self.persona.value,
            step=step_description[:50],
        )

        self._changes = []  # Reset changes for this execution

        try:
            # Step 1: Gather context from target files
            file_context = await self._gather_file_context(
                repo_path=repo_path,
                files=files_affected,
            )

            # Step 2: Build the user prompt
            user_prompt = self._build_user_prompt(
                step=step,
                file_context=file_context,
                plan_context=context.get("plan", {}),
            )

            # Step 3: Generate code changes via LLM with tool-calling
            tool_calls = await self._generate_with_tools(user_prompt)

            # Step 4: Process tool calls into ChangeSets
            for tool_call in tool_calls:
                await self._process_tool_call(tool_call, repo_path)

            # Step 5: Run linter on affected files
            await self.call_tool("run_linter_fix", path=repo_path)

            # Step 6: Get the final diff
            diff_result = await self.call_tool("git_diff_staged", path=repo_path)

            # Calculate confidence
            confidence = self._calculate_confidence(
                changes=self._changes,
                diff_result=diff_result,
            )

            return self.build_output(
                ui_title=f"💻 Code Updated: {step_description[:50]}",
                ui_subtitle=self._generate_subtitle(),
                technical_reasoning=self._format_changes(),
                confidence_score=confidence,
            )

        except LLMValidationError as e:
            logger.warning(
                "coder_validation_error",
                task_id=str(task_id),
                error=str(e),
            )
            return self.build_output(
                ui_title="⚠️ Code Generation Issue",
                ui_subtitle="The code generation didn't produce valid output. Please review.",
                technical_reasoning=json.dumps({
                    "error": str(e),
                    "raw_response": e.raw_response,
                }, indent=2),
                confidence_score=0.3,
            )

        except LLMClientError as e:
            logger.error(
                "coder_llm_error",
                task_id=str(task_id),
                error=str(e),
            )
            return self.build_output(
                ui_title="❌ Code Generation Failed",
                ui_subtitle="Unable to generate code changes due to an API error.",
                technical_reasoning=json.dumps({"error": str(e)}, indent=2),
                confidence_score=0.0,
            )

    async def _gather_file_context(
        self,
        repo_path: str,
        files: list[str],
    ) -> str:
        """Gather signatures and context from target files."""
        context_parts = []

        for file_path in files[:5]:  # Limit to 5 files
            full_path = f"{repo_path}/{file_path}"
            result = await self.call_tool("get_file_signatures", path=full_path)

            if result.success and result.result:
                context_parts.append(f"## {file_path}\n{result.result}")

        return "\n\n".join(context_parts) if context_parts else "No file context available."

    def _build_user_prompt(
        self,
        step: dict,
        file_context: str,
        plan_context: dict,
    ) -> str:
        """Build the user prompt for the LLM."""
        return f"""## Your Task
{step.get('description', 'Implement the required changes')}

## Files to Modify
{', '.join(step.get('files_affected', ['(not specified)']))}

## Context from Existing Files
{file_context}

## Plan Summary
{plan_context.get('summary', 'No plan summary available')}

## Instructions
**IMPORTANT: Write COMPLETE, WORKING implementations. Do NOT use placeholders like `pass`, `return 42`, or `# TODO`.**

1. Use `search_codebase` or `get_file_signatures` if you need more context about existing code
2. For NEW files: Use `create_new_module` with FULL implementation including:
   - All imports needed
   - Best SWE Practices
   - Analyze your code step by step logically thinking about all implications
   - Complete class/function definitions with real logic
   - Proper error handling and type hints
   - Docstrings explaining what each function does
3. For EXISTING files: Use `edit_file_snippet` to make targeted changes
4. Include appropriate tests if the step involves testable functionality

You MUST use the tools to make changes. Never output raw code in your response.
Write production-ready code that would pass a senior engineer's code review."""

    async def _generate_with_tools(
        self,
        user_prompt: str,
    ) -> list[dict]:
        """Generate code using LLM with tool-calling."""
        result = await self.llm_client.generate_with_tools(
            prompt=user_prompt,
            system_prompt=self.system_prompt,
            tools=CODER_TOOLS,
            model_name=self.model_name,
        )

        # Defensive handling - result should be (text, tool_calls) tuple
        if isinstance(result, tuple) and len(result) == 2:
            _, tool_calls = result
        else:
            logger.warning("unexpected_generate_with_tools_result", result_type=type(result).__name__)
            return []

        # Ensure tool_calls is a list of dicts
        if not isinstance(tool_calls, list):
            logger.warning("tool_calls_not_list", tool_calls_type=type(tool_calls).__name__)
            return []

        # Filter out any non-dict entries
        valid_calls = []
        for tc in tool_calls:
            if isinstance(tc, dict) and "name" in tc:
                valid_calls.append(tc)
            else:
                logger.warning("invalid_tool_call_entry", entry_type=type(tc).__name__)

        return valid_calls

    async def _process_tool_call(
        self,
        tool_call: dict,
        repo_path: str,
    ) -> None:
        """Process a tool call from the LLM into a ChangeSet."""
        tool_name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})

        if tool_name == "edit_file_snippet":
            # Execute the edit
            result = await self.call_tool(
                "edit_file_snippet",
                path=f"{repo_path}/{arguments.get('file_path', '')}",
                original=arguments.get("original_code", ""),
                replacement=arguments.get("new_code", ""),
            )

            if result.success:
                # Create ChangeSet
                change = ChangeSet(
                    file_path=arguments.get("file_path", ""),
                    action="modify",
                    diff=self._generate_diff(
                        arguments.get("original_code", ""),
                        arguments.get("new_code", ""),
                    ),
                    explanation=arguments.get("explanation", ""),
                )
                self._changes.append(change)
                logger.info("edit_file_success", file=arguments.get("file_path"))
            else:
                # Log failure but still track the attempt
                logger.warning(
                    "edit_file_failed",
                    file=arguments.get("file_path"),
                    error=result.error,
                    result_data=str(result.result)[:200] if result.result else None,
                )

        elif tool_name == "create_new_module":
            result = await self.call_tool(
                "create_new_module",
                path=f"{repo_path}/{arguments.get('file_path', '')}",
                content=arguments.get("content", ""),
            )

            if result.success:
                change = ChangeSet(
                    file_path=arguments.get("file_path", ""),
                    action="create",
                    diff=f"+++ {arguments.get('file_path', '')}\n{arguments.get('content', '')}",
                    explanation=arguments.get("explanation", ""),
                )
                self._changes.append(change)
                logger.info("create_new_module_success", file=arguments.get("file_path"))
            else:
                logger.warning(
                    "create_new_module_failed",
                    file=arguments.get("file_path"),
                    error=result.error,
                    result_data=str(result.result)[:200] if result.result else None,
                )

        elif tool_name in ["search_codebase", "get_file_signatures"]:
            # These are perception tools - just execute them
            await self.call_tool(tool_name, **arguments)

    def _generate_diff(self, original: str, new: str) -> str:
        """Generate a simple unified diff."""
        from difflib import unified_diff

        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = unified_diff(
            original_lines,
            new_lines,
            fromfile="original",
            tofile="modified",
        )

        return "".join(diff)

    def _calculate_confidence(
        self,
        changes: list[ChangeSet],
        diff_result: Any,
    ) -> float:
        """Calculate confidence in the changes."""
        if not changes:
            return 0.5  # No changes made

        base_confidence = 0.85

        # Lower confidence for many files changed
        if len(changes) > 5:
            base_confidence -= 0.15
        elif len(changes) > 3:
            base_confidence -= 0.1

        # Boost confidence if consistent with plan
        return max(0.4, min(1.0, base_confidence))

    def _generate_subtitle(self) -> str:
        """Generate user-friendly subtitle."""
        if not self._changes:
            return "No changes were required for this step."

        file_count = len(self._changes)
        actions = set(c.action for c in self._changes)

        if "create" in actions and "modify" in actions:
            return f"Created and modified {file_count} file(s) following existing code patterns."
        elif "create" in actions:
            return f"Created {file_count} new file(s) with proper structure and documentation."
        else:
            return f"Modified {file_count} file(s) with minimal, surgical changes."

    def _format_changes(self) -> str:
        """Format changes for technical_reasoning field."""
        if not self._changes:
            return json.dumps({"changes": [], "message": "No changes required"})

        return json.dumps({
            "changes": [
                {
                    "file_path": c.file_path,
                    "action": c.action,
                    "explanation": c.explanation,
                    "diff": c.diff[:500] if c.diff else "",  # Truncate long diffs
                }
                for c in self._changes
            ],
            "total_files": len(self._changes),
        }, indent=2)
