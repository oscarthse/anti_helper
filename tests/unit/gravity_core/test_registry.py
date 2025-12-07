"""
Unit Tests for Tool Registry

Tests the tool registration, dispatch, and OpenAI-compatible schema generation.
"""

import pytest
import asyncio
from typing import Any

# Add project paths
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "libs"))

from gravity_core.tools.registry import ToolRegistry, tool


class TestToolDecorator:
    """Tests for the @tool decorator."""

    def test_tool_decorator_registers_function(self, clean_tool_registry):
        """Test that @tool decorator registers a function."""

        @tool(description="Test tool")
        def my_test_tool(value: str) -> str:
            """A test tool."""
            return f"Result: {value}"

        assert "my_test_tool" in clean_tool_registry._tools
        assert clean_tool_registry._tools["my_test_tool"] == my_test_tool

    def test_tool_decorator_with_custom_name(self, clean_tool_registry):
        """Test that @tool decorator supports custom name."""

        @tool(name="custom_name", description="Test tool")
        def original_name(value: str) -> str:
            return value

        assert "custom_name" in clean_tool_registry._tools
        assert "original_name" not in clean_tool_registry._tools

    def test_tool_decorator_generates_schema(self, clean_tool_registry):
        """Test that @tool decorator generates JSON schema."""

        @tool(description="Adds two numbers")
        def add_numbers(a: int, b: int) -> int:
            """Add two integers together."""
            return a + b

        schema = clean_tool_registry._schemas.get("add_numbers")
        assert schema is not None
        assert schema["name"] == "add_numbers"
        assert schema["description"] == "Adds two numbers"
        assert "parameters" in schema


class TestToolRegistry:
    """Tests for the ToolRegistry class."""

    def test_get_existing_tool(self, clean_tool_registry):
        """Test retrieving an existing tool."""

        @tool(description="Test")
        def existing_tool() -> str:
            return "exists"

        retrieved = clean_tool_registry.get("existing_tool")
        assert retrieved == existing_tool

    def test_get_nonexistent_tool(self, clean_tool_registry):
        """Test that getting nonexistent tool returns None."""
        result = clean_tool_registry.get("nonexistent_tool")
        assert result is None

    def test_list_all_tools(self, clean_tool_registry):
        """Test listing all registered tools."""

        @tool(description="Tool 1")
        def tool_one() -> str:
            return "one"

        @tool(description="Tool 2")
        def tool_two() -> str:
            return "two"

        all_tools = clean_tool_registry.list_all()
        assert "tool_one" in all_tools
        assert "tool_two" in all_tools

    def test_list_for_openai(self, clean_tool_registry):
        """Test generating OpenAI-compatible function definitions."""

        @tool(description="Read a file")
        def read_file(path: str) -> str:
            """Read file contents."""
            return f"Contents of {path}"

        openai_format = clean_tool_registry.list_for_openai()

        assert len(openai_format) == 1
        assert openai_format[0]["type"] == "function"
        assert openai_format[0]["function"]["name"] == "read_file"
        assert "parameters" in openai_format[0]["function"]

    def test_list_for_openai_filters_by_names(self, clean_tool_registry):
        """Test filtering tools by names for OpenAI format."""

        @tool(description="Tool A")
        def tool_a() -> str:
            return "a"

        @tool(description="Tool B")
        def tool_b() -> str:
            return "b"

        @tool(description="Tool C")
        def tool_c() -> str:
            return "c"

        filtered = clean_tool_registry.list_for_openai(names=["tool_a", "tool_c"])

        assert len(filtered) == 2
        names = [t["function"]["name"] for t in filtered]
        assert "tool_a" in names
        assert "tool_c" in names
        assert "tool_b" not in names


class TestToolExecution:
    """Tests for tool execution with error handling."""

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self, clean_tool_registry):
        """Test executing a synchronous tool."""

        @tool(description="Sync tool")
        def sync_tool(value: str) -> str:
            return f"Processed: {value}"

        result = await clean_tool_registry.execute("sync_tool", {"value": "test"})

        assert result["success"] is True
        assert result["result"] == "Processed: test"
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_execute_async_tool(self, clean_tool_registry):
        """Test executing an asynchronous tool."""

        @tool(description="Async tool")
        async def async_tool(value: str) -> str:
            await asyncio.sleep(0.01)
            return f"Async: {value}"

        result = await clean_tool_registry.execute("async_tool", {"value": "test"})

        assert result["success"] is True
        assert result["result"] == "Async: test"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, clean_tool_registry):
        """Test executing a nonexistent tool returns error."""
        result = await clean_tool_registry.execute("nonexistent", {})

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_tool_with_exception(self, clean_tool_registry):
        """Test that tool exceptions are caught and returned as errors."""

        @tool(description="Failing tool")
        def failing_tool(path: str) -> str:
            raise FileNotFoundError(f"File not found: {path}")

        result = await clean_tool_registry.execute("failing_tool", {"path": "/nonexistent"})

        assert result["success"] is False
        assert "FileNotFoundError" in result["error"]
        assert "/nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_with_value_error(self, clean_tool_registry):
        """Test handling of ValueError in tool execution."""

        @tool(description="Validation tool")
        def validate_input(value: int) -> int:
            if value < 0:
                raise ValueError("Value must be non-negative")
            return value * 2

        result = await clean_tool_registry.execute("validate_input", {"value": -5})

        assert result["success"] is False
        assert "ValueError" in result["error"]
        assert "non-negative" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_with_permission_error(self, clean_tool_registry):
        """Test handling of PermissionError in tool execution."""

        @tool(description="Protected tool")
        def access_protected() -> str:
            raise PermissionError("Access denied to protected resource")

        result = await clean_tool_registry.execute("access_protected", {})

        assert result["success"] is False
        assert "PermissionError" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_tracks_duration(self, clean_tool_registry):
        """Test that execution tracks duration in milliseconds."""

        @tool(description="Slow tool")
        async def slow_tool() -> str:
            await asyncio.sleep(0.1)  # 100ms
            return "done"

        result = await clean_tool_registry.execute("slow_tool", {})

        assert result["success"] is True
        assert result["duration_ms"] >= 100


class TestToolSchemaGeneration:
    """Tests for JSON Schema generation from tool signatures."""

    def test_schema_with_basic_types(self, clean_tool_registry):
        """Test schema generation for basic Python types."""

        @tool(description="Basic types")
        def basic_types(
            name: str,
            count: int,
            ratio: float,
            enabled: bool,
        ) -> dict:
            return {"name": name, "count": count}

        schema = clean_tool_registry._schemas.get("basic_types")
        params = schema["parameters"]["properties"]

        assert params["name"]["type"] == "string"
        assert params["count"]["type"] == "integer"
        assert params["ratio"]["type"] == "number"
        assert params["enabled"]["type"] == "boolean"

    def test_schema_with_optional_params(self, clean_tool_registry):
        """Test schema generation for optional parameters."""
        from typing import Optional

        @tool(description="Optional params")
        def optional_params(
            required_param: str,
            optional_param: Optional[str] = None,
        ) -> str:
            return required_param

        schema = clean_tool_registry._schemas.get("optional_params")
        required = schema["parameters"].get("required", [])

        assert "required_param" in required
        # Optional params should not be in required
        assert "optional_param" not in required

    def test_schema_with_list_params(self, clean_tool_registry):
        """Test schema generation for list parameters."""

        @tool(description="List params")
        def list_params(items: list[str]) -> int:
            return len(items)

        schema = clean_tool_registry._schemas.get("list_params")
        params = schema["parameters"]["properties"]

        assert params["items"]["type"] == "array"
