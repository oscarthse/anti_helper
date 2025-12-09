"""
LLM Settings - Role-Based Configuration

Centralized configuration for LLM behavior per agent role.
This module provides the single source of truth for model names,
temperatures, and other LLM parameters.

Design Philosophy:
- Singleton config dict loaded at module import (process-scoped)
- Frozen dataclasses for immutability
- Easy to extend with additional parameters
- Future: Can be loaded from YAML/JSON/DB for n8n-style configurability

Usage:
    from gravity_core.llm.settings import get_config

    config = get_config(AgentPersona.CODER_BE)
    temperature = config.temperature
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gravity_core.schema import AgentPersona


@dataclass(frozen=True)
class AgentLLMConfig:
    """
    Role-specific LLM configuration.

    Frozen for immutability - these are constants once loaded.

    Attributes:
        temperature: LLM temperature (0.0-1.0). Lower = more deterministic.
        model_name: Default model to use for this role.

    Future extensions:
        - max_tokens: Per-role token limits
        - top_p: Nucleus sampling parameter
        - frequency_penalty: Repetition control
    """

    temperature: float
    model_name: str = "gpt-4o"


# =============================================================================
# Role-Based Temperature Constants
# =============================================================================
#
# Design rationale:
# - Planner (0.35): Moderate creativity for strategic thinking, but consistent
# - Coders (0.25): Low temp for deterministic, pattern-following code
# - QA (0.25): Low temp for consistent test analysis and fix suggestions
# - Docs (0.6): Higher creativity for natural documentation language
#
# These values can be overridden in the future via:
# - Environment variables
# - Settings file (YAML/JSON)
# - Database configuration
# - UI controls (n8n-style)
# =============================================================================

# Default model for all agents
DEFAULT_MODEL = "gpt-4o"

# Temperature presets by category
TEMPERATURE_DETERMINISTIC = 0.25  # For code generation, analysis
TEMPERATURE_BALANCED = 0.35  # For planning, strategic thinking
TEMPERATURE_CREATIVE = 0.6  # For documentation, explanations


def _build_agent_configs() -> dict:
    """
    Build the agent config dictionary.

    Lazy import to avoid circular dependency with schema.py
    """
    from gravity_core.schema import AgentPersona

    return {
        AgentPersona.PLANNER: AgentLLMConfig(
            temperature=TEMPERATURE_BALANCED,
            model_name=DEFAULT_MODEL,
        ),
        AgentPersona.CODER_BE: AgentLLMConfig(
            temperature=TEMPERATURE_DETERMINISTIC,
            model_name=DEFAULT_MODEL,
        ),
        AgentPersona.CODER_FE: AgentLLMConfig(
            temperature=TEMPERATURE_DETERMINISTIC,
            model_name=DEFAULT_MODEL,
        ),
        AgentPersona.CODER_INFRA: AgentLLMConfig(
            temperature=TEMPERATURE_DETERMINISTIC,
            model_name=DEFAULT_MODEL,
        ),
        AgentPersona.QA: AgentLLMConfig(
            temperature=TEMPERATURE_DETERMINISTIC,
            model_name=DEFAULT_MODEL,
        ),
        AgentPersona.DOCS: AgentLLMConfig(
            temperature=TEMPERATURE_CREATIVE,
            model_name=DEFAULT_MODEL,
        ),
    }


# Singleton config dict - built lazily on first access
_AGENT_LLM_CONFIGS: dict | None = None


def _get_configs() -> dict:
    """Get or initialize the config dictionary."""
    global _AGENT_LLM_CONFIGS
    if _AGENT_LLM_CONFIGS is None:
        _AGENT_LLM_CONFIGS = _build_agent_configs()
    return _AGENT_LLM_CONFIGS


def get_config(persona: AgentPersona) -> AgentLLMConfig:
    """
    Get LLM configuration for an agent persona.

    Args:
        persona: The agent persona to get config for

    Returns:
        AgentLLMConfig with temperature and model settings

    Example:
        config = get_config(AgentPersona.CODER_BE)
        # config.temperature == 0.25
        # config.model_name == "gpt-4o"
    """
    configs = _get_configs()
    # Return config for persona, or a sensible default
    return configs.get(persona, AgentLLMConfig(temperature=0.5, model_name=DEFAULT_MODEL))


def get_all_configs() -> dict:
    """
    Get all agent LLM configurations.

    Returns:
        Dict mapping AgentPersona to AgentLLMConfig

    Useful for debugging and configuration display.
    """
    return _get_configs().copy()
