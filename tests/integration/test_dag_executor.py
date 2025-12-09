"""
Integration Tests for DAG Executor - Workflow Orchestration

Tests the DAG Executor's ability to:
1. Execute task DAGs in topological order
2. Handle empty and single-task DAGs
3. Respect pause/resume signals
4. Enforce timeouts
5. Handle task failures gracefully
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Repository, Task, TaskStatus
from backend.app.services.dag_executor import DAGExecutor


class TestDAGExecutorBasics:
    """Basic execution tests for DAG Executor."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="test-repo",
            path="/tmp/test-dag-repo",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def root_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a root task for testing."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Test DAG execution with sufficient length",
            title="root-task",
            status=TaskStatus.EXECUTING,
            task_plan={"summary": "Test plan", "steps": []},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.mark.asyncio
    async def test_execute_empty_dag(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that DAG with no subtasks completes successfully."""
        # Mock the documentation phase to avoid LLM calls
        with patch.object(DAGExecutor, "_run_documentation_phase", new_callable=AsyncMock):
            executor = DAGExecutor(
                session=db_session,
                root_task=root_task,
                repo=test_repo,
                context={"user_request": "test", "repo_path": "/tmp"},
            )

            result = await executor.execute()

        assert result.success is True
        assert result.tasks_completed == 0
        assert result.paused_for_review is False

    @pytest.mark.asyncio
    async def test_all_tasks_complete_detection(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that _all_tasks_complete correctly detects completion."""
        # Create some subtasks
        subtask1 = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            parent_task_id=root_task.id,
            user_request="Subtask 1",
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        subtask2 = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            parent_task_id=root_task.id,
            user_request="Subtask 2",
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add_all([subtask1, subtask2])
        await db_session.flush()

        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        # Not all complete yet
        assert await executor._all_tasks_complete() is False

        # Mark second task complete
        subtask2.status = TaskStatus.COMPLETED
        await db_session.flush()

        assert await executor._all_tasks_complete() is True


class TestDAGExecutorSignals:
    """Tests for pause/resume/terminate signal handling."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="signal-test-repo",
            path="/tmp/signal-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def root_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a root task for testing."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Test signal handling with sufficient length",
            status=TaskStatus.EXECUTING,
            task_plan={"summary": "Test", "steps": []},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.mark.asyncio
    async def test_check_signals_continue(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that EXECUTING status returns CONTINUE signal."""
        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        signal = await executor._check_signals()
        assert signal == "CONTINUE"

    @pytest.mark.asyncio
    async def test_check_signals_paused(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that PAUSED status returns PAUSED signal."""
        root_task.status = TaskStatus.PAUSED
        await db_session.flush()

        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        signal = await executor._check_signals()
        assert signal == "PAUSED"

    @pytest.mark.asyncio
    async def test_check_signals_terminated_on_failed(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that FAILED status returns TERMINATED signal."""
        root_task.status = TaskStatus.FAILED
        await db_session.flush()

        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        signal = await executor._check_signals()
        assert signal == "TERMINATED"


class TestDAGExecutorTimeout:
    """Tests for timeout enforcement."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="timeout-test-repo",
            path="/tmp/timeout-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def root_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a root task for testing."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Test timeout enforcement with sufficient length",
            status=TaskStatus.EXECUTING,
            task_plan={"summary": "Test", "steps": []},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.mark.asyncio
    async def test_timeout_detection(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that timeout is detected correctly."""
        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        # Initially not timed out
        assert executor._is_timed_out() is False

        # Manually set start time to past
        from datetime import timedelta

        executor._start_time = datetime.now(UTC) - timedelta(seconds=700)

        # Now should be timed out (default is 600s)
        assert executor._is_timed_out() is True

    @pytest.mark.asyncio
    async def test_timeout_enforcement(
        self, db_session: AsyncSession, root_task: Task, test_repo: Repository
    ):
        """Test that timed out execution returns error."""
        # Create subtask that would need execution
        subtask = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            parent_task_id=root_task.id,
            user_request="Subtask that should timeout",
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(subtask)
        await db_session.flush()

        executor = DAGExecutor(
            session=db_session,
            root_task=root_task,
            repo=test_repo,
            context={"user_request": "test", "repo_path": "/tmp"},
        )

        # Set start time to past the timeout
        from datetime import timedelta

        executor._start_time = datetime.now(UTC) - timedelta(seconds=700)

        result = await executor.execute()

        assert result.success is False
        assert "timed out" in result.error.lower()


class TestDAGExecutorTaskExecution:
    """Tests for single task execution within the DAG."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="exec-test-repo",
            path="/tmp/exec-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def root_task_with_subtask(self, db_session: AsyncSession, test_repo: Repository) -> dict:
        """Create a root task with one subtask."""
        root = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Root task for execution test with sufficient length",
            title="root",
            status=TaskStatus.EXECUTING,
            task_plan={
                "summary": "Test",
                "steps": [{"step_id": "step-1", "order": 1, "files_affected": []}],
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(root)
        await db_session.flush()

        subtask = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            parent_task_id=root.id,
            user_request="Subtask for a detailed operation",
            title="step-1",
            status=TaskStatus.PENDING,
            task_plan={"files_affected": []},  # No files to verify
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(subtask)
        await db_session.flush()

        return {"root": root, "subtask": subtask}

    @pytest.mark.asyncio
    async def test_execute_single_task_dag(
        self,
        db_session: AsyncSession,
        root_task_with_subtask: dict,
        test_repo: Repository,
    ):
        """Test that a single-task DAG executes and marks complete."""
        root = root_task_with_subtask["root"]
        _subtask = root_task_with_subtask["subtask"]  # noqa: F841

        # Mock TaskExecutor to return success immediately
        mock_execution_result = MagicMock()
        mock_execution_result.success = True
        mock_execution_result.changeset = {}
        mock_execution_result.files_written = []

        with (
            patch("backend.app.workers.task_executor.TaskExecutor") as MockTaskExecutor,
            patch.object(DAGExecutor, "_run_documentation_phase", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = mock_execution_result
            MockTaskExecutor.return_value = mock_instance

            executor = DAGExecutor(
                session=db_session,
                root_task=root,
                repo=test_repo,
                context={"user_request": "test", "repo_path": "/tmp"},
            )

            result = await executor.execute()

        assert result.success is True
        assert result.tasks_completed == 1
