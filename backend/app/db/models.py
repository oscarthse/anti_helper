"""
Database Models - SQLAlchemy Async Models

These models represent the single source of truth for all state
in the Antigravity Dev platform.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class TaskDependency(Base):
    """
    DAG Edges: Represents a 'Blocker' relationship.

    blocker_task_id MUST be completed before blocked_task_id can proceed.
    """
    __tablename__ = "task_dependencies"

    blocker_task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id"), primary_key=True)
    blocked_task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id"), primary_key=True)

    # Metadata for the edge
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeNode(Base):
    """
    The Blackboard: Semantic State Persistence.

    Represents a unit of knowledge (Fact, Schema, Decision) tied to a Task.
    Nodes form a knowledge graph that child tasks can inherit.
    """
    __tablename__ = "knowledge_nodes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tasks.id"), nullable=False)

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    task: Mapped["Task"] = relationship("Task", back_populates="knowledge_nodes")



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
    PAUSED = "paused"


class Repository(Base):
    """
    A managed repository.

    Represents a codebase that agents can operate on.
    """

    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Project metadata (populated by ProjectMap)
    project_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(50), nullable=True)

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
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    repo_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("repositories.id"),
        nullable=False,
    )
    parent_task_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("tasks.id"),
        nullable=True,
    )

    # Task definition
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Current state
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    current_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Planning output
    task_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Contract / Definition of Done
    definition_of_done: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)

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

    # Recursion
    subtasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent_task",
        cascade="all, delete-orphan",
    )
    parent_task: Mapped["Task"] = relationship(
        "Task",
        back_populates="subtasks",
        remote_side="Task.id",
    )

    # Blackboard
    knowledge_nodes: Mapped[list["KnowledgeNode"]] = relationship(
        "KnowledgeNode",
        back_populates="task",
        cascade="all, delete-orphan",
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
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    task_id: Mapped[UUID] = mapped_column(
        Uuid,
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
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)

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
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    task_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id"),
        nullable=False,
    )
    agent_log_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("agent_logs.id"),
        nullable=False,
    )

    # Change details
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, modify, delete
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    # Foreign key to repository
    repo_id: Mapped[UUID] = mapped_column(
        Uuid,
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
    description: Mapped[str | None] = mapped_column(
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
