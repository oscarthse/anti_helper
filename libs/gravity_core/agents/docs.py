"""
DOCS Agent - The Technical Scribe

Executes after code passes tests. Analyzes verified ChangeSets and
generates high-quality documentation updates using LLM.

Key Responsibilities:
1. Update README.md with new features/changes
2. Add entries to CHANGELOG.md
3. Improve inline docstrings in modified code
4. Ensure documentation reflects the actual code (not the original request)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from gravity_core.base import BaseAgent
from gravity_core.llm import LLMClient, LLMClientError
from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    ChangeSet,
    DocUpdateLog,
    ToolCall,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# System Prompt (Technical Scribe Persona)
# =============================================================================


DOCS_SYSTEM_PROMPT = """You are a Senior Technical Writer - the project's docs guardian.

## Your Persona
You write documentation like Stripe writes API docs - clear, accurate, and developer-friendly.
You believe that every code change deserves accurate documentation.

## Your Mission
Analyze the verified code changes (ChangeSets) and generate precise documentation updates.

## CRITICAL RULE
Your ONLY input is the final, verified ChangeSet (the actual code that passed tests).
Do NOT use the original user request - document what the code DOES, not what was asked.

## Your Three Atomic Tasks
Execute these in order:
1. **CHANGELOG**: Add a user-friendly entry summarizing the change
2. **README**: Update if the change affects setup, usage, or core features
3. **DOCSTRINGS**: Add/improve docstrings for new/modified functions

## Documentation Standards
- **CHANGELOG**: Follow Keep a Changelog format (Added, Changed, Fixed, Removed)
- **README**: Match existing style, be concise, include code examples
- **DOCSTRINGS**: Use Google or NumPy style, include Args, Returns, Raises

## Tool Usage
You MUST use `edit_file_snippet` to apply documentation changes.
Never output raw documentation content - always use tools.

## Output Requirements
For each documentation task, generate a ToolCall with:
- file_path: The documentation file to update
- original_code: The exact section to replace (or "" for new content)
- new_code: The updated documentation
- explanation: Why this update is needed"""


# =============================================================================
# Tool Definitions for LLM
# =============================================================================


DOCS_TOOLS = [
    {
        "name": "update_changelog",
        "description": "Add a new entry to CHANGELOG.md. Use Keep a Changelog format.",
        "parameters": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Version string (e.g., 'Unreleased', '1.2.0')",
                },
                "category": {
                    "type": "string",
                    "enum": ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"],
                    "description": "Change category following Keep a Changelog",
                },
                "entry": {
                    "type": "string",
                    "description": "The changelog entry text (user-friendly description)",
                },
            },
            "required": ["version", "category", "entry"],
        },
    },
    {
        "name": "update_readme",
        "description": "Update a section of README.md to reflect code changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": (
                        "Which section to update (e.g., 'Installation', 'Usage', 'Configuration')"
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["append", "replace", "insert"],
                    "description": "How to apply the update",
                },
                "content": {
                    "type": "string",
                    "description": "The new or updated content in Markdown",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this README update is needed",
                },
            },
            "required": ["section", "action", "content", "reason"],
        },
    },
    {
        "name": "add_docstring",
        "description": "Add or update a docstring for a function or class.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python file",
                },
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the function or class to document",
                },
                "docstring": {
                    "type": "string",
                    "description": "The complete docstring content (Google style)",
                },
            },
            "required": ["file_path", "symbol_name", "docstring"],
        },
    },
]


# =============================================================================
# DocsAgent Implementation
# =============================================================================


class DocsAgent(BaseAgent):
    """
    The DOCS Agent - Technical Scribe persona.

    Analyzes verified ChangeSets and generates documentation updates
    using LLM for high-quality, consistent documentation.
    """

    persona = AgentPersona.DOCS
    system_prompt = DOCS_SYSTEM_PROMPT
    available_tools = [
        # Manipulation tools (for applying changes)
        "edit_file_snippet",
        "create_new_module",
        # Perception tools (for analysis)
        "scan_repo_structure",
        "search_codebase",
        "get_file_signatures",
    ]

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model_name: str = "gpt-4o",
        **kwargs: Any,
    ) -> None:
        """
        Initialize Docs Agent.

        Args:
            llm_client: LLMClient instance (created if not provided)
            model_name: LLM model to use
        """
        super().__init__(**kwargs)

        self.model_name = model_name
        self.llm_client = llm_client or LLMClient()
        self._doc_changes: list[ChangeSet] = []
        self._tool_calls_made: list[ToolCall] = []

        logger.info("docs_initialized", model=model_name)

    async def execute(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """
        Generate documentation for verified code changes.

        Args:
            task_id: The task being documented
            context: Should contain:
                - changes: List of ChangeSet dicts from Coder
                - repo_path: Path to repository
                - plan_summary: Optional summary from TaskPlan

        Returns:
            AgentOutput with DocUpdateLog details
        """
        repo_path = context.get("repo_path", ".")
        changes = context.get("changes", [])
        plan_summary = context.get("plan_summary", "")

        logger.info(
            "docs_starting",
            task_id=str(task_id),
            change_count=len(changes),
        )

        self._doc_changes = []
        self._tool_calls_made = []

        try:
            # =================================================================
            # Phase 1: ANALYSIS - Build prompt from ChangeSets
            # =================================================================

            if not changes:
                return self._build_no_changes_output()

            # Get existing documentation structure
            doc_structure = await self._scan_documentation(repo_path)

            # =================================================================
            # Phase 2: GENERATION - Use LLM to generate doc updates
            # =================================================================

            doc_tool_calls = await self._generate_documentation_updates(
                changes=changes,
                repo_path=repo_path,
                doc_structure=doc_structure,
                plan_summary=plan_summary,
            )

            # =================================================================
            # Phase 3: APPLICATION - Apply each documentation update
            # =================================================================

            for tool_call in doc_tool_calls:
                await self._apply_doc_update(tool_call, repo_path)

            # Build the update log
            doc_log = DocUpdateLog(
                files_updated=[c.file_path for c in self._doc_changes],
                changes=self._doc_changes,
                summary=self._generate_summary(),
            )

            confidence = 0.9 if self._doc_changes else 0.75

            return self.build_output(
                ui_title="📝 Documentation Updated",
                ui_subtitle=self._generate_subtitle(),
                technical_reasoning=json.dumps({
                    "doc_log": doc_log.model_dump(mode='json'),
                    "tool_calls": [tc.model_dump(mode='json') for tc in self._tool_calls_made],
                }, indent=2),
                confidence_score=confidence,
                tool_calls=self._tool_calls_made,
            )

        except LLMClientError as e:
            logger.error(
                "docs_llm_error",
                task_id=str(task_id),
                error=str(e),
            )
            return self.build_output(
                ui_title="⚠️ Documentation Generation Failed",
                ui_subtitle="Unable to generate documentation due to an API error.",
                technical_reasoning=json.dumps({"error": str(e)}, indent=2),
                confidence_score=0.3,
            )

    async def _scan_documentation(self, repo_path: str) -> dict:
        """Scan repository for existing documentation files."""
        doc_files = {
            "has_readme": False,
            "has_changelog": False,
            "readme_sections": [],
        }

        # Check for README
        readme_result = await self.call_tool(
            "get_file_signatures",
            path=f"{repo_path}/README.md",
        )
        if readme_result.success:
            doc_files["has_readme"] = True

        # Check for CHANGELOG
        changelog_result = await self.call_tool(
            "search_codebase",
            pattern="CHANGELOG",
            path=repo_path,
        )
        if changelog_result.success and changelog_result.result:
            doc_files["has_changelog"] = True

        return doc_files

    async def _generate_documentation_updates(
        self,
        changes: list[dict],
        repo_path: str,
        doc_structure: dict,
        plan_summary: str,
    ) -> list[dict]:
        """Use LLM to generate documentation update tool calls."""

        # Build comprehensive prompt with all changes
        prompt = self._build_doc_prompt(
            changes=changes,
            doc_structure=doc_structure,
            plan_summary=plan_summary,
        )

        # Generate documentation via LLM with tools
        # generate_with_tools returns (text_response, tool_calls) tuple
        _, tool_calls = await self.llm_client.generate_with_tools(
            prompt=prompt,
            system_prompt=DOCS_SYSTEM_PROMPT,
            tools=DOCS_TOOLS,
            model=self.model_name,
            tool_choice="auto",
        )

        return tool_calls if isinstance(tool_calls, list) else []

    def _build_doc_prompt(
        self,
        changes: list[dict],
        doc_structure: dict,
        plan_summary: str,
    ) -> str:
        """Build the prompt for documentation generation."""
        changes_text = ""
        for i, change in enumerate(changes[:10], 1):  # Limit to 10 changes
            changes_text += f"""
### Change {i}
- **File**: {change.get('file_path', 'unknown')}
- **Action**: {change.get('action', 'modify')}
- **Explanation**: {change.get('explanation', 'No explanation provided')}

```diff
{change.get('diff', 'No diff available')[:1000]}
```
"""

        return f"""## Documentation Update Request

### Project Documentation Status
- README.md exists: {doc_structure.get('has_readme', False)}
- CHANGELOG.md exists: {doc_structure.get('has_changelog', False)}

### Summary of Changes
{plan_summary or 'No summary provided'}

### Verified Code Changes (ChangeSets)
These changes have passed all tests and are ready for documentation.
{changes_text}

## Your Tasks
1. **CHANGELOG**: Create a user-friendly changelog entry for these changes
   - Use "Unreleased" as the version
   - Categorize as Added, Changed, Fixed, etc.

2. **README**: Only update if the changes affect:
   - Installation or setup instructions
   - Usage examples or API
   - Configuration options
   - Dependencies

3. **DOCSTRINGS**: For any NEW functions added, generate proper docstrings

Generate the appropriate tool calls for each documentation update needed."""

    async def _apply_doc_update(
        self,
        tool_call: dict,
        repo_path: str,
    ) -> None:
        """Apply a documentation update tool call."""
        tool_name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})

        if tool_name == "update_changelog":
            change = await self._update_changelog(
                repo_path=repo_path,
                version=args.get("version", "Unreleased"),
                category=args.get("category", "Changed"),
                entry=args.get("entry", ""),
            )
            if change:
                self._doc_changes.append(change)
                self._tool_calls_made.append(ToolCall(
                    tool_name="edit_file_snippet",
                    arguments={"file": "CHANGELOG.md", **args},
                    result="Changelog updated",
                    success=True,
                    duration_ms=0,
                ))

        elif tool_name == "update_readme":
            change = await self._update_readme(
                repo_path=repo_path,
                section=args.get("section", ""),
                action=args.get("action", "append"),
                content=args.get("content", ""),
            )
            if change:
                self._doc_changes.append(change)
                self._tool_calls_made.append(ToolCall(
                    tool_name="edit_file_snippet",
                    arguments={"file": "README.md", **args},
                    result="README updated",
                    success=True,
                    duration_ms=0,
                ))

        elif tool_name == "add_docstring":
            change = await self._add_docstring(
                repo_path=repo_path,
                file_path=args.get("file_path", ""),
                symbol_name=args.get("symbol_name", ""),
                docstring=args.get("docstring", ""),
            )
            if change:
                self._doc_changes.append(change)
                self._tool_calls_made.append(ToolCall(
                    tool_name="edit_file_snippet",
                    arguments=args,
                    result="Docstring added",
                    success=True,
                    duration_ms=0,
                ))

    async def _update_changelog(
        self,
        repo_path: str,
        version: str,
        category: str,
        entry: str,
    ) -> ChangeSet | None:
        """Update CHANGELOG.md with a new entry."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Build the changelog entry
        new_entry = f"\n### [{version}] - {today}\n\n#### {category}\n\n- {entry}\n"

        # Apply via tool
        result = await self.call_tool(
            "edit_file_snippet",
            path=f"{repo_path}/CHANGELOG.md",
            original="# Changelog",
            replacement=f"# Changelog\n{new_entry}",
        )

        if result.success:
            return ChangeSet(
                file_path="CHANGELOG.md",
                action="modify",
                diff=f"+{new_entry}",
                explanation=f"Added {category.lower()} entry: {entry[:50]}...",
            )

        # If no existing changelog, create one
        create_result = await self.call_tool(
            "create_new_module",
            path=f"{repo_path}/CHANGELOG.md",
            content=(
                f"# Changelog\n\nAll notable changes to this project "
                f"will be documented in this file.\n{new_entry}"
            ),
        )

        if create_result.success:
            return ChangeSet(
                file_path="CHANGELOG.md",
                action="create",
                diff="+Created CHANGELOG.md with initial entry",
                explanation=f"Created changelog with {category.lower()} entry",
            )

        return None

    async def _update_readme(
        self,
        repo_path: str,
        section: str,
        action: str,
        content: str,
    ) -> ChangeSet | None:
        """Update a section of README.md."""
        # Find the section in README
        search_result = await self.call_tool(
            "search_codebase",
            pattern=f"## {section}",
            path=f"{repo_path}/README.md",
        )

        if not search_result.success:
            logger.warning(
                "readme_section_not_found",
                section=section,
            )
            return None

        # Apply the edit
        if action == "append":
            result = await self.call_tool(
                "edit_file_snippet",
                path=f"{repo_path}/README.md",
                original=f"## {section}",
                replacement=f"## {section}\n\n{content}",
            )
        else:
            # For replace, need more context
            result = await self.call_tool(
                "edit_file_snippet",
                path=f"{repo_path}/README.md",
                original=f"## {section}",
                replacement=f"## {section}\n\n{content}",
            )

        if result.success:
            return ChangeSet(
                file_path="README.md",
                action="modify",
                diff=f"+Updated section: {section}",
                explanation=f"Updated README {section} section",
            )

        return None

    async def _add_docstring(
        self,
        repo_path: str,
        file_path: str,
        symbol_name: str,
        docstring: str,
    ) -> ChangeSet | None:
        """Add or update a docstring for a function/class."""
        full_path = f"{repo_path}/{file_path}" if not file_path.startswith("/") else file_path

        # Find the function definition
        search_result = await self.call_tool(
            "search_codebase",
            pattern=f"def {symbol_name}",
            path=full_path,
        )

        if not search_result.success:
            # Try class
            search_result = await self.call_tool(
                "search_codebase",
                pattern=f"class {symbol_name}",
                path=full_path,
            )

        if not search_result.success:
            logger.warning(
                "symbol_not_found",
                symbol=symbol_name,
                file=file_path,
            )
            return None

        # Format the docstring with proper indentation
        formatted_docstring = f'    """{docstring}\n    """'

        # Apply the docstring (this is simplified - real impl would be more precise)
        result = await self.call_tool(
            "edit_file_snippet",
            path=full_path,
            original=f"def {symbol_name}",
            replacement=f"def {symbol_name}\n{formatted_docstring}",
        )

        if result.success:
            return ChangeSet(
                file_path=file_path,
                action="modify",
                diff=f"+Added docstring to {symbol_name}",
                explanation=f"Added documentation for {symbol_name}",
            )

        return None

    def _build_no_changes_output(self) -> AgentOutput:
        """Build output when no changes require documentation."""
        return self.build_output(
            ui_title="📝 Documentation Review Complete",
            ui_subtitle="No documentation updates required for this task.",
            technical_reasoning=json.dumps({
                "status": "no_updates_needed",
                "reason": "No code changes were provided to document",
            }, indent=2),
            confidence_score=0.95,
        )

    def _generate_subtitle(self) -> str:
        """Generate user-friendly subtitle."""
        if not self._doc_changes:
            return "No documentation updates were required."

        files = set(c.file_path for c in self._doc_changes)
        count = len(self._doc_changes)

        if "CHANGELOG.md" in files and "README.md" in files:
            return f"Updated {count} documentation file(s) including CHANGELOG and README."
        elif "CHANGELOG.md" in files:
            return "Added changelog entry for the recent changes."
        elif "README.md" in files:
            return "Updated README to reflect the new functionality."
        else:
            return f"Improved documentation in {count} file(s)."

    def _generate_summary(self) -> str:
        """Generate a summary of documentation updates."""
        if not self._doc_changes:
            return "No documentation updates required."

        parts = []
        for change in self._doc_changes:
            parts.append(f"- {change.file_path}: {change.explanation}")

        return "\n".join(parts)

    def get_doc_changes(self) -> list[ChangeSet]:
        """Get the documentation changes made."""
        return self._doc_changes
