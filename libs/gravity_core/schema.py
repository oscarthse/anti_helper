"""
GravityCore Schema - The Explainability Contract

This module defines the mandatory Pydantic models for all agent outputs.
Every agent action must be logged with a clear, user-facing explanation,
adhering to the Explainability First mandate.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# =============================================================================
# Agent Personas
# =============================================================================


class AgentPersona(str, Enum):
    """Agent personas in the workflow."""

    PLANNER = "planner"  # Product Manager - Analyzes and plans
    CODER_BE = "coder_be"  # Backend Engineer
    CODER_FE = "coder_fe"  # Frontend Engineer
    CODER_INFRA = "coder_infra"  # Infrastructure Engineer
    QA = "qa"  # Tester/Debugger
    DOCS = "docs"  # Scribe - Documentation


# =============================================================================
# Tool Call Schema
# =============================================================================


class ToolCall(BaseModel):
    """
    Atomic action requested by an agent.

    Each tool call represents a single operation like reading a file,
    running a command, or making an edit.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for this tool call")
    tool_name: str = Field(description="Name of the tool being called")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the tool"
    )
    result: str | None = Field(
        default=None,
        description="Result returned by the tool (populated after execution)"
    )
    success: bool = Field(
        default=True,
        description="Whether the tool execution succeeded"
    )
    error: str | None = Field(
        default=None,
        description="Error message if the tool failed"
    )
    duration_ms: int | None = Field(
        default=None,
        description="Execution time in milliseconds"
    )


# =============================================================================
# Core Agent Output - The Explainability Contract
# =============================================================================


class AgentOutput(BaseModel):
    """
    Mandatory output schema for all agents.

    This enforces the separation of technical logs from user-facing
    explanations, ensuring every action is explainable.
    """

    # User-facing fields (for THE FACE)
    ui_title: str = Field(
        description="Short, engaging header for the frontend card. "
        "Example: 'Initializing Database Migration'"
    )
    ui_subtitle: str = Field(
        description="The 'What does this mean?' explanation for the user. "
        "Example: 'I am creating a new column to store encrypted customer data.'"
    )

    # Technical fields (for audit logs)
    technical_reasoning: str = Field(
        description="Detailed logic for audit logs and debugging. "
        "This is the 'why' behind the agent's decision."
    )

    # Action tracking
    tool_calls: list[ToolCall] = Field(
        default_factory=list,
        description="The atomic actions the agent requested"
    )

    # Confidence for human review triggering
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent's certainty (0.0-1.0). Low scores trigger human review."
    )

    # Metadata
    agent_persona: AgentPersona = Field(
        description="The persona of the agent that generated this output"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this output was generated"
    )

    @property
    def requires_review(self) -> bool:
        """Check if this output requires human review based on confidence."""
        return self.confidence_score < 0.7


# =============================================================================
# Specialized Output Types
# =============================================================================


class TaskStep(BaseModel):
    """A single step in a task plan."""

    order: int = Field(description="Execution order (1-indexed)")
    description: str = Field(description="What this step accomplishes")
    agent_persona: AgentPersona = Field(description="Which agent should execute this")
    estimated_tokens: int | None = Field(
        default=None,
        description="Estimated LLM tokens for this step"
    )
    dependencies: list[int] = Field(
        default_factory=list,
        description="Step numbers this step depends on"
    )
    files_affected: list[str] = Field(
        default_factory=list,
        description="Files that will be modified"
    )


class TaskPlan(BaseModel):
    """
    Output from the PLANNER agent.

    Defines the atomic steps required to complete a task,
    which agents should execute each step, and in what order.
    """

    task_id: UUID = Field(default_factory=uuid4)
    summary: str = Field(description="High-level description of the plan")
    steps: list[TaskStep] = Field(description="Ordered list of steps to execute")
    estimated_complexity: int = Field(
        ge=1,
        le=10,
        description="Complexity score (1=simple, 10=very complex)"
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="All files that will be modified"
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Potential risks or considerations"
    )

    @property
    def total_steps(self) -> int:
        return len(self.steps)


class ChangeSet(BaseModel):
    """
    Output from CODER agents.

    Represents a set of changes to a file, including the unified diff
    and a human-readable explanation.
    """

    file_path: str = Field(description="Path to the file being modified")
    action: str = Field(
        description="Type of change: 'create', 'modify', 'delete'"
    )
    diff: str = Field(
        description="Unified diff format showing the changes"
    )
    explanation: str = Field(
        description="Human-readable explanation of what the change does"
    )
    language: str | None = Field(
        default=None,
        description="Programming language of the file"
    )
    line_count_before: int | None = Field(default=None)
    line_count_after: int | None = Field(default=None)


class ExecutionRun(BaseModel):
    """
    Output from the QA agent.

    Represents the result of running a command in the sandbox,
    including all output and the success/failure status.
    """

    command: str = Field(description="The command that was executed")
    working_directory: str = Field(description="Directory where command ran")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    exit_code: int = Field(description="Exit code (0 = success)")
    duration_ms: int = Field(description="Execution time in milliseconds")

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        parts = []
        if self.stdout:
            parts.append(f"STDOUT:\n{self.stdout}")
        if self.stderr:
            parts.append(f"STDERR:\n{self.stderr}")
        return "\n\n".join(parts)


class DocUpdateLog(BaseModel):
    """
    Output from the DOCS agent.

    Tracks updates made to documentation files after code changes
    pass all tests.
    """

    files_updated: list[str] = Field(
        description="List of documentation files that were updated"
    )
    changes: list[ChangeSet] = Field(
        description="The actual changes made to each file"
    )
    summary: str = Field(
        description="Summary of documentation updates for release notes"
    )


# =============================================================================
# Task State
# =============================================================================


class TaskStatus(str, Enum):
    """State machine for task execution."""

    PENDING = "pending"  # Task created, not yet started
    PLANNING = "planning"  # PLANNER is analyzing
    PLAN_REVIEW = "plan_review"  # Waiting for human approval of plan
    EXECUTING = "executing"  # CODER is implementing
    TESTING = "testing"  # QA is running tests
    DOCUMENTING = "documenting"  # DOCS is updating docs
    COMPLETED = "completed"  # All done successfully
    FAILED = "failed"  # Something went wrong
    REVIEW_REQUIRED = "review_required"  # Low confidence, needs human input
