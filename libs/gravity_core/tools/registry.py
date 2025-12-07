"""
Tool Registry - Core tool management system.

This module provides the central registry for all tools available to agents.
Tools are registered with their schemas for LLM function calling.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import inspect
import structlog
from gravity_core.schema import ToolCall

logger = structlog.get_logger()
# Map Python types to JSON schema types
TYPE_MAPPING = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


class ToolRegistry:
    """
    Central registry for all agent tools.

    Tools are registered by name with their schemas (for LLM function calling)
    and implementations. The registry handles execution, timing, and error handling.
    """

    _tools: dict[str, Callable] = {}
    _schemas: dict[str, dict] = {}

    @classmethod
    def register(
        cls,
        name: str,
        func: Callable,
        schema: dict | None = None,
        description: str = "",
        category: str = "general",
    ) -> None:
        """
        Register a tool with the registry.

        Args:
            name: Unique tool name
            func: The tool implementation
            schema: JSON Schema for parameters (for LLM function calling)
            description: Human-readable description
            category: Tool category for grouping
        """
        cls._tools[name] = func

        # Auto-generate schema if not provided
        tool_schema = schema or cls._generate_schema(func)

        cls._schemas[name] = {
            "name": name,
            "description": description,
            "category": category,
            "parameters": tool_schema,
        }
        logger.debug("tool_registered", name=name, category=category)

    @staticmethod
    def _generate_schema(func: Callable) -> dict:
        """Generate JSON Schema from function signature."""
        sig = inspect.signature(func)
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            # Skip self/cls for methods if missed (though tools are usually functions)
            if name in ("self", "cls"):
                continue

            # Get type annotation
            py_type = param.annotation

            # Simple type mapping
            schema_type = TYPE_MAPPING.get(py_type, "string")

            # Handle complex types
            if hasattr(py_type, "__origin__"):
                if py_type.__origin__ is list:
                    schema_type = "array"
                elif py_type.__origin__ is dict:
                    schema_type = "object"
                # Handle Union/Optional (e.g. str | None)
                elif hasattr(py_type, "__args__") and type(None) in py_type.__args__:
                    # Find the non-None type
                    non_none = next((t for t in py_type.__args__ if t is not type(None)), str)
                    schema_type = TYPE_MAPPING.get(non_none, "string")

            prop = {"type": schema_type}
            if schema_type == "array":
                prop["items"] = {"type": "string"} # Default to string items for simplicity

            properties[name] = prop

            if param.default == inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @classmethod
    def get(cls, name: str) -> Callable | None:
        """Get a tool implementation by name."""
        return cls._tools.get(name)

    @classmethod
    def get_schema(cls, name: str) -> dict | None:
        """Get a tool's schema by name."""
        return cls._schemas.get(name)

    @classmethod
    def list_tools(cls, category: str | None = None) -> list[dict]:
        """
        List all registered tools with their schemas.

        Args:
            category: Optional filter by category

        Returns:
            List of tool schemas
        """
        tools = list(cls._schemas.values())
        if category:
            tools = [t for t in tools if t.get("category") == category]
        return tools

    @classmethod
    def list_for_openai(cls, tool_names: list[str] | None = None) -> list[dict]:
        """
        Format tools for OpenAI function calling API.

        Args:
            tool_names: Optional list to filter by name

        Returns:
            List of tools in OpenAI function format
        """
        tools = []
        for name, schema in cls._schemas.items():
            if tool_names and name not in tool_names:
                continue
            tools.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["parameters"],
                },
            })
        return tools

    @classmethod
    async def execute(cls, name: str, **kwargs: Any) -> ToolCall:
        """
        Execute a tool and return a ToolCall result.

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            ToolCall object with execution result and metadata
        """
        tool = cls.get(name)
        if not tool:
            return ToolCall(
                tool_name=name,
                arguments=kwargs,
                success=False,
                error=f"Tool '{name}' not found in registry",
                duration_ms=0,
            )

        start_time = time.perf_counter()
        try:
            # Support both sync and async tools
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**kwargs)
            else:
                result = tool(**kwargs)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return ToolCall(
                tool_name=name,
                arguments=kwargs,
                result=str(result) if result is not None else None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("tool_execution_failed", tool=name, error=str(e))
            return ToolCall(
                tool_name=name,
                arguments=kwargs,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )


def tool(
    name: str | None = None,
    description: str = "",
    schema: dict | None = None,
    category: str = "general",
) -> Callable:
    """
    Decorator to register a function as a tool.

    Example:
        @tool(
            name="read_file",  # Optional, defaults to function name
            description="Read contents of a file",
            ...
        )
        async def read_file(path: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        ToolRegistry.register(
            name=tool_name,
            func=func,
            schema=schema,
            description=description,
            category=category,
        )
        return func
    return decorator
