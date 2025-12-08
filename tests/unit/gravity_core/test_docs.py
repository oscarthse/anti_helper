"""
Unit Tests for Docs Agent

Tests documentation generation including:
- CHANGELOG updates
- README updates
- Docstring generation
- LLM tool-call handling
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestDocsAgentExecution:
    """Tests for DocsAgent.execute() with mocked LLM."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client for testing."""
        client = MagicMock()
        client.generate_with_tools = AsyncMock()
        return client

    @pytest.fixture
    def mock_changeset(self):
        """Create a sample ChangeSet for testing."""
        return {
            "file_path": "libs/gravity_core/agents/new_agent.py",
            "action": "create",
            "diff": "+class NewAgent:\n+    pass",
            "explanation": "Added new agent implementation",
        }

    @pytest.fixture
    def docs_agent(self, mock_llm_client):
        """Create DocsAgent with mocked LLM."""
        from gravity_core.agents.docs import DocsAgent

        agent = DocsAgent(
            llm_client=mock_llm_client,
            model_name="gpt-4o-test",
        )

        # Mock the call_tool method
        agent.call_tool = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_generates_changelog_entry(self, docs_agent, mock_llm_client, mock_changeset):
        """Test that DocsAgent generates a changelog entry for code changes."""
        # Configure LLM to return changelog tool call
        mock_llm_client.generate_with_tools.return_value = (
            "Generating changelog...",
            {
                "tool_calls": [
                    {
                        "name": "update_changelog",
                        "arguments": {
                            "version": "Unreleased",
                            "category": "Added",
                            "entry": "New agent implementation for enhanced workflow",
                        },
                    },
                ],
            }
        )

        # Mock tool calls
        docs_agent.call_tool.return_value = MagicMock(
            success=True,
            result="Updated",
        )

        context = {
            "repo_path": "/test/repo",
            "changes": [mock_changeset],
            "plan_summary": "Added new agent",
        }

        output = await docs_agent.execute(uuid4(), context)

        # Verify LLM was called
        mock_llm_client.generate_with_tools.assert_called_once()

        # Output should contain documentation updates
        assert output.ui_title == "📝 Documentation Updated"
        assert output.confidence_score >= 0.75

    @pytest.mark.asyncio
    async def test_generates_multiple_doc_updates(
        self, docs_agent, mock_llm_client, mock_changeset
    ):
        """Test that DocsAgent can generate multiple documentation updates."""
        # Configure LLM to return multiple tool calls
        mock_llm_client.generate_with_tools.return_value = (
            "Updating docs...",
            {
                "tool_calls": [
                    {
                        "name": "update_changelog",
                        "arguments": {
                            "version": "Unreleased",
                            "category": "Added",
                            "entry": "New feature added",
                        },
                    },
                    {
                        "name": "update_readme",
                        "arguments": {
                            "section": "Usage",
                            "action": "append",
                            "content": "## New Feature\n\nDescription here.",
                            "reason": "Document new feature",
                        },
                    },
                ],
            }
        )

        # Mock successful tool executions
        docs_agent.call_tool.return_value = MagicMock(
            success=True,
            result="Success",
        )

        context = {
            "repo_path": "/test/repo",
            "changes": [mock_changeset],
            "plan_summary": "Major feature addition",
        }

        await docs_agent.execute(uuid4(), context)

        # Verify both updates are in the output (changelog and readme)
        assert docs_agent.call_tool.call_count >= 2

    @pytest.mark.asyncio
    async def test_no_changes_returns_gracefully(self, docs_agent, mock_llm_client):
        """Test that DocsAgent handles empty changes gracefully."""
        context = {
            "repo_path": "/test/repo",
            "changes": [],
            "plan_summary": "",
        }

        output = await docs_agent.execute(uuid4(), context)

        assert output.ui_title == "📝 Documentation Review Complete"
        assert "No documentation updates" in output.ui_subtitle
        assert output.confidence_score >= 0.9

        # LLM should not be called for empty changes
        mock_llm_client.generate_with_tools.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, docs_agent, mock_llm_client, mock_changeset):
        """Test that DocsAgent handles LLM errors gracefully."""
        from gravity_core.llm import LLMClientError

        mock_llm_client.generate_with_tools.side_effect = LLMClientError("API Error")

        context = {
            "repo_path": "/test/repo",
            "changes": [mock_changeset],
        }

        output = await docs_agent.execute(uuid4(), context)

        assert "Failed" in output.ui_title
        assert output.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_generates_docstring_for_new_function(self, docs_agent, mock_llm_client):
        """Test that DocsAgent generates docstrings for new functions."""
        mock_llm_client.generate_with_tools.return_value = (
            "Adding docstring...",
            {
                "tool_calls": [
                    {
                        "name": "add_docstring",
                        "arguments": {
                            "file_path": "libs/gravity_core/utils/helper.py",
                            "symbol_name": "calculate_metrics",
                            "docstring": (
                                "Calculate metrics for the given data.\n\n"
                                "Args:\n    data: Input data dict\n\n"
                                "Returns:\n    Computed metrics"
                            ),
                        },
                    },
                ],
            }
        )

        docs_agent.call_tool.return_value = MagicMock(
            success=True,
            result="Docstring added",
        )

        context = {
            "repo_path": "/test/repo",
            "changes": [
                {
                    "file_path": "libs/gravity_core/utils/helper.py",
                    "action": "create",
                    "diff": "+def calculate_metrics(data):\n+    return {}",
                    "explanation": "Added metrics calculation",
                },
            ],
        }

        await docs_agent.execute(uuid4(), context)

        # Should have docstring update in tool calls
        assert docs_agent.call_tool.call_count >= 1


class TestDocsAgentPromptBuilding:
    """Tests for prompt construction logic."""

    @pytest.fixture
    def docs_agent(self):
        """Create DocsAgent without LLM for unit testing."""
        from gravity_core.agents.docs import DocsAgent
        return DocsAgent()

    def test_build_doc_prompt_includes_changes(self, docs_agent):
        """Test that the documentation prompt includes change details."""
        changes = [
            {
                "file_path": "api/routes.py",
                "action": "modify",
                "diff": "+@router.get('/health')\n+def health(): pass",
                "explanation": "Added health check endpoint",
            },
        ]

        prompt = docs_agent._build_doc_prompt(
            changes=changes,
            doc_structure={"has_readme": True, "has_changelog": True},
            plan_summary="Add health check",
        )

        assert "api/routes.py" in prompt
        assert "health check" in prompt.lower()
        assert "CHANGELOG" in prompt
        assert "README" in prompt

    def test_build_doc_prompt_limits_changes(self, docs_agent):
        """Test that prompt limits number of changes to prevent token overflow."""
        # Create 15 changes
        changes = [
            {
                "file_path": f"file_{i}.py",
                "action": "modify",
                "diff": f"+line {i}",
                "explanation": f"Change {i}",
            }
            for i in range(15)
        ]

        prompt = docs_agent._build_doc_prompt(
            changes=changes,
            doc_structure={},
            plan_summary="",
        )

        # Should only include first 10 (limit in implementation)
        assert "file_9.py" in prompt
        assert "file_14.py" not in prompt  # 11th+ should be excluded


class TestDocsAgentHelpers:
    """Tests for helper methods."""

    @pytest.fixture
    def docs_agent(self):
        """Create DocsAgent for testing."""
        from gravity_core.agents.docs import ChangeSet, DocsAgent
        agent = DocsAgent()
        agent._doc_changes = [
            ChangeSet(
                file_path="CHANGELOG.md",
                action="modify",
                diff="+Added feature",
                explanation="Changelog entry",
            ),
            ChangeSet(
                file_path="README.md",
                action="modify",
                diff="+Usage docs",
                explanation="Updated usage",
            ),
        ]
        return agent

    def test_generate_subtitle_changelog_and_readme(self, docs_agent):
        """Test subtitle generation with both files updated."""
        subtitle = docs_agent._generate_subtitle()

        assert "CHANGELOG" in subtitle
        assert "README" in subtitle

    def test_generate_summary_lists_files(self, docs_agent):
        """Test summary includes all updated files."""
        summary = docs_agent._generate_summary()

        assert "CHANGELOG.md" in summary
        assert "README.md" in summary

    def test_get_doc_changes_returns_changes(self, docs_agent):
        """Test get_doc_changes returns the changes list."""
        changes = docs_agent.get_doc_changes()

        assert len(changes) == 2
        assert changes[0].file_path == "CHANGELOG.md"
