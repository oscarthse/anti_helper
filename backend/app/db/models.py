"""
Database Models - SQLAlchemy Async Models

These models represent the single source of truth for all state
in the Antigravity Dev platform.
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class TaskStatus(str, enum.Enum):
    """State machine for task execution."""

    PENDING = "pending"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    EXECUTING = "executing"
    TESTING = "testing"
    DOCUMENTING = "documenting"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class Repository(Base):
    """
    A managed repository.

    Represents a codebase that agents can operate on.
    """

    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Project metadata (populated by ProjectMap)
    project_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    framework: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class Task(Base):
    """
    Main task entity - single source of truth.

    Represents a user request that agents will execute.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    repo_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id"),
        nullable=False,
    )

    # Task definition
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Current state
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    current_agent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Planning output
    task_plan: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="tasks",
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        "AgentLog",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="AgentLog.created_at",
    )


class AgentLog(Base):
    """
    Immutable log of all agent actions.

    This is the explainability audit trail - every action
    an agent takes is recorded with both technical and
    user-friendly explanations.
    """

    __tablename__ = "agent_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
    )

    # Agent identification
    agent_persona: Mapped[str] = mapped_column(String(50), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # User-facing fields (The Explainability Contract)
    ui_title: Mapped[str] = mapped_column(String(255), nullable=False)
    ui_subtitle: Mapped[str] = mapped_column(Text, nullable=False)

    # Technical fields
    technical_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Confidence and review
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    requires_review: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="agent_logs",
    )


class ChangeSet(Base):
    """
    Record of code changes made by agents.

    Each changeset represents modifications to a file,
    stored as a unified diff.
    """

    __tablename__ = "changesets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
    )
    agent_log_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_logs.id"),
        nullable=False,
    )

    # Change details
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, modify, delete
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lines_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    applied: Mapped[bool] = mapped_column(default=False, nullable=False)
    reverted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class RepositorySecret(Base):
    """
    Secure storage for repository secrets (API keys, credentials).

    Secrets are encrypted at rest using Fernet symmetric encryption.
    The encryption key is stored in the ANTIGRAVITY_ENCRYPTION_KEY
    environment variable and never in the database.
    """

    __tablename__ = "repository_secrets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key to repository
    repo_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id"),
        nullable=False,
    )

    # Secret identification
    key_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Environment variable name (e.g., 'STRIPE_API_KEY')",
    )

    # Encrypted secret value
    encrypted_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Fernet-encrypted secret value",
    )

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of what this secret is used for",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationship
    repository: Mapped["Repository"] = relationship(
        "Repository",
        backref="secrets",
    )

    def __repr__(self) -> str:
        return f"<RepositorySecret {self.key_name} for repo {self.repo_id}>"
