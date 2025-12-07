"""
Tool Registry - Core tool management system.

This module provides the central registry for all tools available to agents.
Tools are registered with their schemas for LLM function calling.
"""

import asyncio
import time
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger()


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
        schema: Optional[dict] = None,
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
        cls._schemas[name] = {
            "name": name,
            "description": description,
            "category": category,
            "parameters": schema or {"type": "object", "properties": {}},
        }
        logger.debug("tool_registered", name=name, category=category)

    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        """Get a tool implementation by name."""
        return cls._tools.get(name)

    @classmethod
    def get_schema(cls, name: str) -> Optional[dict]:
        """Get a tool's schema by name."""
        return cls._schemas.get(name)

    @classmethod
    def list_tools(cls, category: Optional[str] = None) -> list[dict]:
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
    def list_for_openai(cls, tool_names: Optional[list[str]] = None) -> list[dict]:
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
    async def execute(cls, name: str, **kwargs: Any) -> dict:
        """
        Execute a tool and return structured result.

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            Dict with 'success', 'result', 'error', 'duration_ms'
        """
        tool = cls.get(name)
        if not tool:
            return {
                "success": False,
                "result": None,
                "error": f"Tool '{name}' not found in registry",
                "duration_ms": 0,
            }

        start_time = time.perf_counter()
        try:
            # Support both sync and async tools
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**kwargs)
            else:
                result = tool(**kwargs)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return {
                "success": True,
                "result": result,
                "error": None,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("tool_execution_failed", tool=name, error=str(e))
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "duration_ms": duration_ms,
            }


def tool(
    name: str,
    description: str = "",
    schema: Optional[dict] = None,
    category: str = "general",
) -> Callable:
    """
    Decorator to register a function as a tool.

    Example:
        @tool(
            name="read_file",
            description="Read contents of a file",
            schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            },
            category="perception"
        )
        async def read_file(path: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        ToolRegistry.register(
            name=name,
            func=func,
            schema=schema,
            description=description,
            category=category,
        )
        return func
    return decorator
