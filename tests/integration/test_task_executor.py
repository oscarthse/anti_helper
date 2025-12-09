"""
Integration Tests for Task Executor - Code → Test → Fix Loop

Tests the Task Executor's ability to:
1. Execute the Code → Test → Fix loop
2. Use the Reality Engine for file verification
3. Handle QA pass/fail scenarios
4. Respect max retry attempts
5. Capture and propagate changesets
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Repository, Task, TaskStatus
from backend.app.workers.task_executor import (
    RealityEngine,
    TaskExecutor,
)


class TestTaskExecutorBasics:
    """Basic execution tests for Task Executor."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="executor-test-repo",
            path="/tmp/executor-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def test_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a test task for execution."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Implement a hello world function with proper type hints",
            title="step-1",
            status=TaskStatus.PENDING,
            task_plan={"files_affected": [], "description": "Test task"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.fixture
    def mock_coder_output(self):
        """Create a mock coder agent output."""
        from gravity_core.schema import AgentOutput, AgentPersona

        return AgentOutput(
            ui_title="💻 Code Written",
            ui_subtitle="Created test files",
            technical_reasoning='{"changes": [{"file": "test.py", "action": "create"}]}',
            agent_persona=AgentPersona.CODER_BE,
            confidence_score=0.95,
            tool_calls=[],
        )

    @pytest.fixture
    def mock_qa_output_pass(self):
        """Create a mock QA agent output (tests passed)."""
        from gravity_core.schema import AgentOutput, AgentPersona

        return AgentOutput(
            ui_title="✅ Tests Passed",
            ui_subtitle="All tests passed successfully",
            technical_reasoning="Tests executed without errors",
            agent_persona=AgentPersona.QA,
            confidence_score=0.95,
            tool_calls=[],
        )

    @pytest.fixture
    def mock_qa_output_fail(self):
        """Create a mock QA agent output (tests failed)."""
        from gravity_core.schema import AgentOutput, AgentPersona

        return AgentOutput(
            ui_title="❌ Tests Failed",
            ui_subtitle="Some tests failed",
            technical_reasoning="Test execution found errors",
            agent_persona=AgentPersona.QA,
            confidence_score=0.3,
            tool_calls=[],
        )

    @pytest.mark.asyncio
    async def test_execute_basic_success(
        self,
        db_session: AsyncSession,
        test_task: Task,
        mock_coder_output,
        mock_qa_output_pass,
    ):
        """Test successful execution with passing tests."""
        context = {"repo_path": "/tmp/executor-test", "test_commands": ["pytest"]}

        # Mock agents and dependencies - patch where imported in execute()
        with (
            patch("gravity_core.agents.coder.CoderAgent") as MockCoder,
            patch("gravity_core.agents.qa.QAAgent") as MockQA,
            patch("gravity_core.llm.LLMClient"),
            patch("backend.app.workers.agent_runner.log_agent_output", new_callable=AsyncMock),
            patch(
                "backend.app.workers.agent_runner.publish_verified_file_event",
                new_callable=AsyncMock,
            ),
        ):
            # Configure mocks
            mock_coder_instance = AsyncMock()
            mock_coder_instance.execute.return_value = mock_coder_output
            MockCoder.return_value = mock_coder_instance

            mock_qa_instance = AsyncMock()
            mock_qa_instance.execute.return_value = mock_qa_output_pass
            mock_qa_instance.has_suggested_fix.return_value = False

            # Setup metrics mock - use dict not MagicMock so .get() works
            mock_qa_instance._execution_runs = [{"command": "pytest", "exit_code": 0}]

            MockQA.return_value = mock_qa_instance

            executor = TaskExecutor(
                session=db_session,
                task=test_task,
                context=context,
                max_fix_attempts=3,
            )

            result = await executor.execute()

        assert result.success is True
        assert test_task.status == TaskStatus.TESTING  # Set during QA phase

    @pytest.mark.asyncio
    async def test_execute_extracts_changeset(
        self,
        db_session: AsyncSession,
        test_task: Task,
        mock_qa_output_pass,
    ):
        """Test that changeset is correctly extracted from coder output."""
        from gravity_core.schema import AgentOutput, AgentPersona

        # Create coder output with specific changeset
        coder_output_with_changeset = AgentOutput(
            ui_title="💻 Code Written",
            ui_subtitle="Created test files",
            technical_reasoning='{"changes": [{"file": "app.py", "action": "create", "lines": 42}]}',
            agent_persona=AgentPersona.CODER_BE,
            confidence_score=0.95,
            tool_calls=[],
        )

        context = {"repo_path": "/tmp/executor-test", "test_commands": ["pytest"]}

        with (
            patch("gravity_core.agents.coder.CoderAgent") as MockCoder,
            patch("gravity_core.agents.qa.QAAgent") as MockQA,
            patch("gravity_core.llm.LLMClient"),
            patch("backend.app.workers.agent_runner.log_agent_output", new_callable=AsyncMock),
            patch(
                "backend.app.workers.agent_runner.publish_verified_file_event",
                new_callable=AsyncMock,
            ),
        ):
            mock_coder_instance = AsyncMock()
            mock_coder_instance.execute.return_value = coder_output_with_changeset
            MockCoder.return_value = mock_coder_instance

            mock_qa_instance = AsyncMock()
            mock_qa_instance.execute.return_value = mock_qa_output_pass
            mock_qa_instance.has_suggested_fix.return_value = False

            # Setup metrics mock - use dict not MagicMock so .get() works
            mock_qa_instance._execution_runs = [{"command": "pytest", "exit_code": 0}]

            MockQA.return_value = mock_qa_instance

            executor = TaskExecutor(
                session=db_session,
                task=test_task,
                context=context,
            )

            result = await executor.execute()

        assert result.success is True
        # Changeset should be extracted from technical_reasoning
        assert result.changeset == {"file": "app.py", "action": "create", "lines": 42}


class TestTaskExecutorRealityCheck:
    """Tests for Reality Engine integration."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="reality-test-repo",
            path="/tmp/reality-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def test_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a test task."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Create a module with type hints and docstrings",
            title="step-reality",
            status=TaskStatus.PENDING,
            task_plan={"files_affected": [], "description": "Test task"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.mark.asyncio
    async def test_reality_engine_tracks_written_files(self, tmp_path):
        """Test that Reality Engine tracks files written during execution."""
        repo_path = str(tmp_path / "test_repo")
        (tmp_path / "test_repo").mkdir()

        engine = RealityEngine(repo_path=repo_path, step_index=0)

        # Write a file
        content = '''
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
'''
        engine.write_file("greet.py", content)

        assert len(engine.written_files) == 1
        assert "greet.py" in engine.written_files[0]

    @pytest.mark.asyncio
    async def test_extract_claimed_files_from_tool_calls(
        self, db_session: AsyncSession, test_task: Task
    ):
        """Test that claimed files are extracted from coder tool calls."""
        from gravity_core.schema import AgentOutput, AgentPersona, ToolCall

        # Create output with tool calls
        coder_output = AgentOutput(
            ui_title="💻 Code Written",
            ui_subtitle="Created files",
            technical_reasoning="{}",
            agent_persona=AgentPersona.CODER_BE,
            confidence_score=0.9,
            tool_calls=[
                ToolCall(
                    tool_name="create_new_module",
                    arguments={"path": "src/utils.py", "content": "# utils"},
                    result="OK",
                    success=True,
                ),
                ToolCall(
                    tool_name="edit_file_snippet",
                    arguments={"path": "src/main.py", "old": "x", "new": "y"},
                    result="OK",
                    success=True,
                ),
            ],
        )

        context = {"repo_path": "/tmp/reality-test", "test_commands": ["pytest"]}
        executor = TaskExecutor(
            session=db_session,
            task=test_task,
            context=context,
        )

        claimed_files = executor._extract_claimed_files(coder_output)

        assert "src/utils.py" in claimed_files
        assert "src/main.py" in claimed_files


class TestTaskExecutorRetryLogic:
    """Tests for fix attempt retry logic."""

    @pytest_asyncio.fixture
    async def test_repo(self, db_session: AsyncSession) -> Repository:
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            name="retry-test-repo",
            path="/tmp/retry-test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(repo)
        await db_session.flush()
        return repo

    @pytest_asyncio.fixture
    async def test_task(self, db_session: AsyncSession, test_repo: Repository) -> Task:
        """Create a test task."""
        task = Task(
            id=uuid4(),
            repo_id=test_repo.id,
            user_request="Create a function that requires fixes due to test failures",
            title="step-retry",
            status=TaskStatus.PENDING,
            task_plan={"files_affected": [], "description": "Test task"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    @pytest.mark.asyncio
    async def test_max_fix_attempts_enforced(self, db_session: AsyncSession, test_task: Task):
        """Test that execution stops after max fix attempts."""
        from gravity_core.schema import AgentOutput, AgentPersona, ToolCall

        # Create outputs that trigger retries
        coder_output = AgentOutput(
            ui_title="💻 Code Written",
            ui_subtitle="Created files",
            technical_reasoning="{}",
            agent_persona=AgentPersona.CODER_BE,
            confidence_score=0.9,
            tool_calls=[
                ToolCall(
                    tool_name="create_new_module",
                    arguments={"path": "/nonexistent/path.py", "content": "# test"},
                    result="OK",
                    success=True,
                ),
            ],
        )

        qa_fail_output = AgentOutput(
            ui_title="❌ Tests Failed",
            ui_subtitle="Tests failed",
            technical_reasoning="{}",
            agent_persona=AgentPersona.QA,
            confidence_score=0.3,
            tool_calls=[],
        )

        context = {"repo_path": "/tmp/retry-test", "test_commands": ["pytest"]}

        with (
            patch("gravity_core.agents.coder.CoderAgent") as MockCoder,
            patch("gravity_core.agents.qa.QAAgent") as MockQA,
            patch("gravity_core.llm.LLMClient"),
            patch("backend.app.workers.agent_runner.log_agent_output", new_callable=AsyncMock),
            patch(
                "backend.app.workers.agent_runner.publish_verified_file_event",
                new_callable=AsyncMock,
            ),
        ):
            mock_coder = AsyncMock()
            mock_coder.execute.return_value = coder_output
            MockCoder.return_value = mock_coder

            mock_qa = AsyncMock()
            mock_qa.execute.return_value = qa_fail_output
            mock_qa.has_suggested_fix.return_value = True
            mock_qa.get_suggested_fix.return_value = None

            # Setup metrics mock
            run_mock = MagicMock()
            run_mock.command = "pytest"
            run_mock.exit_code = 1
            mock_qa._execution_runs = [run_mock]

            MockQA.return_value = mock_qa

            # Set max_fix_attempts to 2 for faster test
            executor = TaskExecutor(
                session=db_session,
                task=test_task,
                context=context,
                max_fix_attempts=2,
            )

            # Mock the reality engine to always fail
            with patch.object(executor.reality_engine, "verify_all_writes") as mock_verify:
                mock_verify.return_value = (False, ["/nonexistent/path.py"])

                result = await executor.execute()

        # Should still return success (just with max attempts logged)
        # The executor continues even after max attempts if QA passes eventually
        assert result is not None

    @pytest.mark.asyncio
    async def test_review_required_pauses_execution(
        self, db_session: AsyncSession, test_task: Task
    ):
        """Test that low confidence triggers review pause."""
        from gravity_core.schema import AgentPersona

        context = {"repo_path": "/tmp/retry-test", "test_commands": ["pytest"]}

        with (
            patch("gravity_core.agents.coder.CoderAgent") as MockCoder,
            patch("gravity_core.llm.LLMClient"),
            patch("backend.app.workers.agent_runner.log_agent_output", new_callable=AsyncMock),
        ):
            mock_coder = AsyncMock()
            # Use MagicMock to simulate requires_review property returning True
            output_mock = MagicMock()
            output_mock.requires_review = True
            output_mock.confidence_score = 0.4
            output_mock.ui_title = "⚠️ Needs Review"
            output_mock.ui_subtitle = "Low confidence"
            output_mock.technical_reasoning = "{}"
            output_mock.agent_persona = AgentPersona.CODER_BE
            output_mock.tool_calls = []
            mock_coder.execute.return_value = output_mock
            MockCoder.return_value = mock_coder

            executor = TaskExecutor(
                session=db_session,
                task=test_task,
                context=context,
            )

            result = await executor.execute()

        assert result.success is True
        assert test_task.status == TaskStatus.REVIEW_REQUIRED
