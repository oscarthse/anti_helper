"""
GravityCore Base Agent - The Agent Contract

This module defines the base class for all agent personas.
Each agent must implement the execute method and produce
structured output conforming to the Explainability Contract.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import structlog

from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    ToolCall,
)
from gravity_core.tools.registry import ToolRegistry

logger = structlog.get_logger()





class BaseAgent(ABC):
    """
    Base class for all agent personas.

    Each agent has:
    - A persona (PLANNER, CODER_BE, etc.)
    - A system prompt defining its role
    - A list of available tools
    - An output schema (defaults to AgentOutput)

    Subclasses must implement the execute() method.
    """

    persona: AgentPersona
    system_prompt: str
    available_tools: list[str]
    output_schema: type[AgentOutput] = AgentOutput

    def __init__(
        self,
        llm_provider: str = "openai",
        model: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        """
        Initialize the agent.

        Args:
            llm_provider: LLM provider to use ('openai' or 'gemini')
            model: Specific model to use (defaults to provider's best)
            temperature: Sampling temperature (lower = more deterministic)
        """
        self.llm_provider = llm_provider
        self.model = model
        self.temperature = temperature
        self._tool_calls: list[ToolCall] = []

        logger.info(
            "agent_initialized",
            persona=self.persona.value,
            provider=llm_provider,
            model=model,
        )

    @property
    def tools(self) -> list[dict]:
        """Get the schemas for available tools."""
        all_tools = ToolRegistry.list_tools()
        return [t for t in all_tools if t["name"] in self.available_tools]

    async def call_tool(self, tool_name: str, **kwargs: Any) -> ToolCall:
        """
        Execute a tool and track the call.

        This is the primary way agents interact with the environment.
        """
        if tool_name not in self.available_tools:
            result = ToolCall(
                tool_name=tool_name,
                arguments=kwargs,
                success=False,
                error=f"Tool '{tool_name}' not available to {self.persona.value} agent",
                duration_ms=0,
            )
        else:
            result = await ToolRegistry.execute(tool_name, **kwargs)

        self._tool_calls.append(result)
        return result

    def build_output(
        self,
        ui_title: str,
        ui_subtitle: str,
        technical_reasoning: str,
        confidence_score: float,
        tool_calls: list[ToolCall] | None = None,
    ) -> AgentOutput:
        """
        Build the standardized agent output.

        This ensures all agents produce output conforming to
        the Explainability Contract.

        Args:
            ui_title: User-friendly title for the action
            ui_subtitle: User-friendly explanation
            technical_reasoning: Detailed reasoning for audit
            confidence_score: 0.0-1.0 confidence level
            tool_calls: Optional override for tool calls (defaults to self._tool_calls)
        """
        return AgentOutput(
            ui_title=ui_title,
            ui_subtitle=ui_subtitle,
            technical_reasoning=technical_reasoning,
            tool_calls=tool_calls if tool_calls is not None else self._tool_calls.copy(),
            confidence_score=confidence_score,
            agent_persona=self.persona,
        )

    @abstractmethod
    async def execute(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """
        Execute the agent's task and return structured output.

        Args:
            task_id: The ID of the task being executed
            context: Context including user request, repo state, etc.

        Returns:
            AgentOutput conforming to the Explainability Contract
        """
        pass

    async def __call__(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """Allow agents to be called directly."""
        self._tool_calls = []  # Reset tool calls for new execution
        return await self.execute(task_id, context)
