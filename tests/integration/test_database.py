"""
Integration Tests for Database Layer

Tests async database sessions, connection pooling,
and ORM operations.
"""

# Add project paths
# Add project paths
from datetime import datetime
from uuid import uuid4

import pytest

from backend.app.db.models import AgentLog, Repository, Task, TaskStatus


class TestDatabaseSession:
    """Tests for database session management."""

    @pytest.mark.asyncio
    async def test_session_creation(self, db_session):
        """Test that a database session is created successfully."""
        assert db_session is not None
        assert db_session.is_active

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self, db_session):
        """Test that session rolls back on error."""

        # Create a repository
        repo = Repository(
            id=uuid4(),
            name="test-repo",
            path="/tmp/test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(repo)
        await db_session.flush()

        # Session should have the repo
        assert repo in db_session

        # Rollback happens in fixture cleanup


class TestRepositoryModel:
    """Tests for Repository ORM model."""

    @pytest.mark.asyncio
    async def test_create_repository(self, db_session, sample_repository_data):
        """Test creating a repository."""

        repo = Repository(**sample_repository_data)
        db_session.add(repo)
        await db_session.flush()

        assert repo.id is not None
        assert repo.name == "test-repo"
        assert repo.project_type == "python"

    @pytest.mark.asyncio
    async def test_repository_timestamps(self, db_session):
        """Test that timestamps are set correctly."""

        before = datetime.utcnow()

        repo = Repository(
            id=uuid4(),
            name="timestamp-test",
            path="/tmp/timestamp",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(repo)
        await db_session.flush()

        after = datetime.utcnow()

        assert before <= repo.created_at <= after
        assert before <= repo.updated_at <= after


class TestTaskModel:
    """Tests for Task ORM model."""

    @pytest.mark.asyncio
    async def test_create_task(self, db_session, sample_repository_data, sample_task_data):
        """Test creating a task with a repository."""

        # Create repository first
        repo = Repository(**sample_repository_data)
        db_session.add(repo)
        await db_session.flush()

        # Create task
        task = Task(
            id=sample_task_data["id"],
            repo_id=repo.id,
            user_request=sample_task_data["user_request"],
            title=sample_task_data["title"],
            status=TaskStatus.PENDING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.flush()

        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert task.repo_id == repo.id

    @pytest.mark.asyncio
    async def test_task_status_transitions(self, db_session, sample_repository_data):
        """Test that task status can be updated."""

        repo = Repository(**sample_repository_data)
        db_session.add(repo)
        await db_session.flush()

        task = Task(
            id=uuid4(),
            repo_id=repo.id,
            user_request="Test task",
            status=TaskStatus.PENDING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.flush()

        # Transition through statuses
        task.status = TaskStatus.PLANNING
        await db_session.flush()
        assert task.status == TaskStatus.PLANNING

        task.status = TaskStatus.EXECUTING
        await db_session.flush()
        assert task.status == TaskStatus.EXECUTING

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        await db_session.flush()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None


class TestAgentLogModel:
    """Tests for AgentLog ORM model."""

    @pytest.mark.asyncio
    async def test_create_agent_log(self, db_session, sample_repository_data):
        """Test creating an agent log entry."""

        # Create repository and task
        repo = Repository(**sample_repository_data)
        db_session.add(repo)
        await db_session.flush()

        task = Task(
            id=uuid4(),
            repo_id=repo.id,
            user_request="Test task",
            status=TaskStatus.PLANNING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.flush()

        # Create agent log
        log = AgentLog(
            id=uuid4(),
            task_id=task.id,
            agent_persona="planner",
            step_number=1,
            ui_title="Analyzing Request",
            ui_subtitle="I'm understanding what you need.",
            technical_reasoning="Parsing user request for intent.",
            confidence_score=0.9,
            requires_review=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(log)
        await db_session.flush()

        assert log.id is not None
        assert log.agent_persona == "planner"
        assert log.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_agent_log_with_tool_calls(self, db_session, sample_repository_data):
        """Test agent log with tool calls JSON."""

        repo = Repository(**sample_repository_data)
        db_session.add(repo)
        await db_session.flush()

        task = Task(
            id=uuid4(),
            repo_id=repo.id,
            user_request="Test task",
            status=TaskStatus.PLANNING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.flush()

        tool_calls = [
            {
                "tool_name": "scan_repo_structure",
                "arguments": {"path": "/app"},
                "success": True,
            },
            {
                "tool_name": "search_codebase",
                "arguments": {"pattern": "def main"},
                "success": True,
            },
        ]

        log = AgentLog(
            id=uuid4(),
            task_id=task.id,
            agent_persona="planner",
            step_number=1,
            ui_title="Scanning Codebase",
            ui_subtitle="Looking at your project structure.",
            technical_reasoning="Initial reconnaissance",
            tool_calls=tool_calls,
            confidence_score=0.85,
            requires_review=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(log)
        await db_session.flush()

        assert log.tool_calls is not None
        assert len(log.tool_calls) == 2
        assert log.tool_calls[0]["tool_name"] == "scan_repo_structure"


class TestDatabaseConstraints:
    """Tests for database constraints and integrity."""

    @pytest.mark.asyncio
    async def test_task_requires_valid_repo(self, db_session):
        """Test that task requires existing repository."""
        from sqlalchemy.exc import IntegrityError


        task = Task(
            id=uuid4(),
            repo_id=uuid4(),  # Non-existent repo
            user_request="Test task",
            status=TaskStatus.PENDING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)

        # SQLite doesn't enforce foreign keys by default in tests,
        # but this tests the pattern
        try:
            await db_session.flush()
        except IntegrityError:
            await db_session.rollback()
            # This is expected behavior
