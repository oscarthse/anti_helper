"""
Unit Tests for JSON Cleaning in LLM Client

Tests the resilient JSON parsing that handles common LLM output artifacts:
- Markdown code fences (```json ... ```)
- Trailing commas in objects/arrays
- JavaScript-style comments (// and /* */)
- Leading explanatory text
"""

import pytest
from gravity_core.llm.client import LLMClient


class TestJsonCleaning:
    """Tests for _clean_json_response method."""

    @pytest.fixture
    def client(self):
        """Create an LLMClient for testing."""
        return LLMClient()

    def test_clean_json_markdown_fence_with_label(self, client):
        """Test extraction from ```json ... ``` blocks."""
        dirty = """Here is the JSON:
```json
{"key": "value", "count": 42}
```
Hope this helps!"""

        result = client._clean_json_response(dirty)
        assert result == '{"key": "value", "count": 42}'

    def test_clean_json_markdown_fence_without_label(self, client):
        """Test extraction from ``` ... ``` blocks without json label."""
        dirty = """
```
{"items": [1, 2, 3]}
```
"""
        result = client._clean_json_response(dirty)
        assert result == '{"items": [1, 2, 3]}'

    def test_clean_json_trailing_comma_object(self, client):
        """Test removal of trailing comma in objects."""
        dirty = '{"key": "value", "count": 42,}'

        result = client._clean_json_response(dirty)
        assert result == '{"key": "value", "count": 42}'

    def test_clean_json_trailing_comma_array(self, client):
        """Test removal of trailing comma in arrays."""
        dirty = '{"items": [1, 2, 3,]}'

        result = client._clean_json_response(dirty)
        assert result == '{"items": [1, 2, 3]}'

    def test_clean_json_trailing_comma_nested(self, client):
        """Test removal of trailing comma in nested structures."""
        dirty = '{"outer": {"inner": "value",},}'

        result = client._clean_json_response(dirty)
        assert result == '{"outer": {"inner": "value"}}'

    def test_clean_json_line_comment(self, client):
        """Test removal of // line comments."""
        dirty = """{"key": "value"} // This is a comment"""

        result = client._clean_json_response(dirty)
        # The JSON should be extractable (comment removed)
        assert '"key": "value"' in result
        assert "//" not in result

    def test_clean_json_block_comment_prefix(self, client):
        """Test removal of /* */ block comments."""
        dirty = """/* Here's the response */ {"key": "value"}"""

        result = client._clean_json_response(dirty)
        assert result.strip().startswith("{")
        assert "/*" not in result
        assert "*/" not in result

    def test_clean_json_leading_text(self, client):
        """Test extraction when JSON is preceded by explanatory text."""
        dirty = 'Here is your data: {"name": "test"}'

        result = client._clean_json_response(dirty)
        assert result == '{"name": "test"}'

    def test_clean_json_already_clean(self, client):
        """Test that clean JSON passes through unchanged."""
        clean = '{"key": "value", "nested": {"array": [1, 2, 3]}}'

        result = client._clean_json_response(clean)
        assert result == clean

    def test_clean_json_array_input(self, client):
        """Test handling of JSON arrays (not just objects)."""
        dirty = """```json
[{"id": 1}, {"id": 2}]
```"""

        result = client._clean_json_response(dirty)
        assert result == '[{"id": 1}, {"id": 2}]'

    def test_clean_json_multiline_with_mixed_issues(self, client):
        """Test handling of multiple issues combined."""
        dirty = """I'll create a plan for you:
```json
{
    "steps": [
        "step 1",
        "step 2",
    ],
}
```
Let me know if you need changes!"""

        result = client._clean_json_response(dirty)
        # Should handle fence extraction + trailing comma removal
        assert '"steps"' in result
        assert ",]" not in result  # Trailing comma in array removed
        assert ",}" not in result  # Trailing comma in object removed

    def test_clean_json_empty_string(self, client):
        """Test handling of empty input."""
        result = client._clean_json_response("")
        assert result == ""

    def test_clean_json_whitespace_only(self, client):
        """Test handling of whitespace-only input."""
        result = client._clean_json_response("   \n\t  ")
        assert result == ""


class TestJsonCleaningIntegration:
    """Integration tests verifying _validate_response handles dirty JSON."""

    @pytest.fixture
    def client(self):
        """Create an LLMClient for testing."""
        return LLMClient()

    def test_validate_response_with_markdown_fence(self, client):
        """Test _validate_response successfully parses markdown-wrapped JSON."""
        from gravity_core.schema import AgentOutput

        dirty = """```json
{
    "ui_title": "Test Title",
    "ui_subtitle": "Test subtitle",
    "technical_reasoning": "Test reasoning",
    "tool_calls": [],
    "confidence_score": 0.9,
    "agent_persona": "planner"
}
```"""

        result = client._validate_response(dirty, AgentOutput, "test")

        assert isinstance(result, AgentOutput)
        assert result.ui_title == "Test Title"
        assert result.confidence_score == 0.9

    def test_validate_response_with_trailing_comma(self, client):
        """Test _validate_response handles trailing commas."""
        from gravity_core.schema import AgentOutput

        dirty = """{
    "ui_title": "Test Title",
    "ui_subtitle": "Test subtitle",
    "technical_reasoning": "Test reasoning",
    "tool_calls": [],
    "confidence_score": 0.85,
    "agent_persona": "planner",
}"""

        result = client._validate_response(dirty, AgentOutput, "test")

        assert isinstance(result, AgentOutput)
        assert result.confidence_score == 0.85
