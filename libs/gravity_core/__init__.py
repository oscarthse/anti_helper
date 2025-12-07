"""
GravityCore - The Brain of Antigravity Dev

A custom library for multi-agent AI development with structured output
and deep context management.
"""

from gravity_core.schema import (
    AgentOutput,
    ToolCall,
    TaskPlan,
    ChangeSet,
    ExecutionRun,
    DocUpdateLog,
    AgentPersona,
)
from gravity_core.base import BaseAgent
from gravity_core.llm import LLMClient, LLMClientError, LLMValidationError

__version__ = "0.1.0"

__all__ = [
    "AgentOutput",
    "ToolCall",
    "TaskPlan",
    "ChangeSet",
    "ExecutionRun",
    "DocUpdateLog",
    "AgentPersona",
    "BaseAgent",
    "LLMClient",
    "LLMClientError",
    "LLMValidationError",
]
