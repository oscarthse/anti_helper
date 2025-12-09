"""
Unit Tests for Dramatiq Worker

Tests the agent_runner worker orchestration:
- Happy path with mocked PlannerAgent
- State transitions based on confidence score
- Error handling and recovery
- Agent logging to database
"""

# Add project paths
# Add project paths
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestWorkerOrchestration:
    """Tests for the run_task worker orchestration."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_task(self):
        """Create a mock Task object."""
        from backend.app.db.models import TaskStatus

        task = MagicMock()
        task.id = uuid4()
        task.repo_id = uuid4()
        task.user_request = "Add validation to user endpoint"
        task.status = TaskStatus.PENDING
        task.current_agent = None
        task.current_step = 0
        task.task_plan = None
        task.retry_count = 0
        return task

    @pytest.fixture
    def mock_repo(self):
        """Create a mock Repository object."""
        repo = MagicMock()
        repo.id = uuid4()
        repo.path = "/tmp/test-repo"
        repo.name = "Test Repo"
        return repo

    @pytest.fixture
    def mock_agent_output_high_confidence(self):
        """Create a mock AgentOutput with high confidence (≥0.7)."""
        from gravity_core.schema import AgentOutput, AgentPersona

        return AgentOutput(
            ui_title="📋 Strategic Plan: 3 Steps",
            ui_subtitle="Implementation plan for validation",
            technical_reasoning='{"task_plan": {"summary": "Add validation", "steps": []}}',
            tool_calls=[],
            confidence_score=0.85,  # High confidence → EXECUTING
            agent_persona=AgentPersona.PLANNER,
        )

    @pytest.fixture
    def mock_agent_output_low_confidence(self):
        """Create a mock AgentOutput with low confidence (<0.7)."""
        from gravity_core.schema import AgentOutput, AgentPersona

        return AgentOutput(
            ui_title="⚠️ Plan Needs Review",
            ui_subtitle="Plan requires human verification",
            technical_reasoning='{"task_plan": {"summary": "Risky change", "steps": []}}',
            tool_calls=[],
            confidence_score=0.5,  # Low confidence → PLAN_REVIEW
            agent_persona=AgentPersona.PLANNER,
        )

    @pytest.mark.asyncio
    async def test_run_task_happy_path_high_confidence(
        self,
        mock_session,
        mock_task,
        mock_repo,
        mock_agent_output_high_confidence,
    ):
        """
        Test happy path: Task is processed and moves to EXECUTING state.
        """
        from gravity_core.schema import TaskContext

        from backend.app.db.models import TaskStatus
        from backend.app.workers.agent_runner import _run_planning_phase

        # Mock dependencies at their source locations
        with (
            patch("gravity_core.llm.LLMClient") as mock_llm_class,
            patch("gravity_core.memory.project_map.ProjectMap") as mock_pm_class,
            patch("gravity_core.agents.planner.PlannerAgent") as mock_planner_class,
        ):
            # Setup LLMClient mock
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm

            # Setup ProjectMap mock
            mock_pm = MagicMock()
            mock_pm.scan = AsyncMock()
            mock_pm.to_context.return_value = "## Project Context"
            mock_pm_class.return_value = mock_pm

            # Setup PlannerAgent mock
            mock_planner = MagicMock()
            mock_planner.execute = AsyncMock(return_value=mock_agent_output_high_confidence)
            mock_planner_class.return_value = mock_planner

            # Execute with TaskContext object instead of dict
            context = TaskContext(
                task_id=mock_task.id,
                user_request="Add validation",
                repo_path="/tmp",
            )
            success, error = await _run_planning_phase(
                session=mock_session,
                task=mock_task,
                repo=mock_repo,
                context=context,
            )

            # Assert
            assert success is True
            assert error is None
            assert mock_task.status == TaskStatus.EXECUTING
            mock_session.add.assert_called()  # AgentLog was added

    @pytest.mark.asyncio
    async def test_run_task_low_confidence_triggers_review(
        self,
        mock_session,
        mock_task,
        mock_repo,
        mock_agent_output_low_confidence,
    ):
        """
        Test: Low confidence score triggers PLAN_REVIEW state.
        """
        from gravity_core.schema import TaskContext

        from backend.app.db.models import TaskStatus
        from backend.app.workers.agent_runner import _run_planning_phase

        with (
            patch("gravity_core.llm.LLMClient") as mock_llm_class,
            patch("gravity_core.memory.project_map.ProjectMap") as mock_pm_class,
            patch("gravity_core.agents.planner.PlannerAgent") as mock_planner_class,
        ):
            mock_llm_class.return_value = MagicMock()

            mock_pm = MagicMock()
            mock_pm.scan = AsyncMock()
            mock_pm.to_context.return_value = ""
            mock_pm_class.return_value = mock_pm

            mock_planner = MagicMock()
            mock_planner.execute = AsyncMock(return_value=mock_agent_output_low_confidence)
            mock_planner_class.return_value = mock_planner

            # Execute with TaskContext object
            context = TaskContext(
                task_id=mock_task.id,
                user_request="Risky change",
                repo_path="/tmp",
            )
            success, error = await _run_planning_phase(
                session=mock_session,
                task=mock_task,
                repo=mock_repo,
                context=context,
            )

            # Assert: Low confidence → PLAN_REVIEW
            assert success is True
            assert mock_task.status == TaskStatus.PLAN_REVIEW

    @pytest.mark.asyncio
    async def test_agent_log_created_on_plan_output(
        self,
        mock_session,
        mock_task,
        mock_repo,
        mock_agent_output_high_confidence,
    ):
        """
        Test: AgentLog entry is created when PlannerAgent returns.
        """
        from gravity_core.schema import TaskContext

        from backend.app.workers.agent_runner import _run_planning_phase

        with (
            patch("gravity_core.llm.LLMClient") as mock_llm_class,
            patch("gravity_core.memory.project_map.ProjectMap") as mock_pm_class,
            patch("gravity_core.agents.planner.PlannerAgent") as mock_planner_class,
        ):
            mock_llm_class.return_value = MagicMock()

            mock_pm = MagicMock()
            mock_pm.scan = AsyncMock()
            mock_pm.to_context.return_value = ""
            mock_pm_class.return_value = mock_pm

            mock_planner = MagicMock()
            mock_planner.execute = AsyncMock(return_value=mock_agent_output_high_confidence)
            mock_planner_class.return_value = mock_planner

            # Execute with TaskContext object
            context = TaskContext(
                task_id=mock_task.id,
                user_request="Test",
                repo_path="/tmp",
            )
            await _run_planning_phase(
                session=mock_session,
                task=mock_task,
                repo=mock_repo,
                context=context,
            )

            # Assert: session.add was called with an AgentLog
            mock_session.add.assert_called()
            added_obj = mock_session.add.call_args[0][0]

            # Verify it's an AgentLog-like object
            assert hasattr(added_obj, "ui_title")
            assert hasattr(added_obj, "confidence_score")


class TestLogAgentOutput:
    """Tests for the log_agent_output utility function."""

    @pytest.mark.asyncio
    async def test_log_agent_output_creates_entry(self):
        """Test that log_agent_output creates an AgentLog entry."""
        from gravity_core.schema import AgentOutput, AgentPersona

        from backend.app.workers.agent_runner import log_agent_output

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()  # Must be async now

        # Mock get_event_bus
        with patch("backend.app.core.events.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock()
            mock_bus.publish_task_event = AsyncMock()
            mock_get_bus.return_value = mock_bus

            output = AgentOutput(
                ui_title="Test Title",
                ui_subtitle="Test Subtitle",
                technical_reasoning="Test reasoning",
                tool_calls=[],
                confidence_score=0.9,
                agent_persona=AgentPersona.PLANNER,
            )

            await log_agent_output(
                session=mock_session,
                task_id=uuid4(),
                agent_output=output,
                step_number=0,
            )

            # Assert that session.add was called with an AgentLog
            mock_session.add.assert_called_once()
            added_entry = mock_session.add.call_args[0][0]
            assert added_entry.ui_title == "Test Title"
            assert added_entry.confidence_score == 0.9


class TestTaskNotFound:
    """Tests for error handling when task/repo not found."""

    @pytest.mark.asyncio
    async def test_task_not_found_exits_gracefully(self):
        """Test that worker exits gracefully when task not found."""
        from backend.app.workers.agent_runner import _run_task_async

        # Mock database engine and session factory
        with (
            patch("backend.app.workers.agent_runner._create_worker_engine", AsyncMock()),
            patch("backend.app.workers.agent_runner.async_sessionmaker"),
        ):
            await _run_task_async("non-existent-id")


class TestResumeTask:
    """Tests for the resume_task actor."""

    @pytest.mark.asyncio
    async def test_resume_approved_sets_executing(self):
        """Test that approving a task sets status to EXECUTING."""
        from backend.app.db.models import TaskStatus
        from backend.app.workers.agent_runner import _resume_task_async

        mock_task = MagicMock()
        mock_task.status = TaskStatus.PLAN_REVIEW

        with (
            patch("backend.app.workers.agent_runner._create_worker_engine", AsyncMock()),
            patch("backend.app.workers.agent_runner.async_sessionmaker") as mock_factory,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_factory.return_value.return_value = mock_session

            with patch(
                "backend.app.workers.agent_runner._get_task", AsyncMock(return_value=mock_task)
            ):
                await _resume_task_async("task-id", approved=True)

                assert mock_task.status == TaskStatus.EXECUTING

    @pytest.mark.asyncio
    async def test_resume_rejected_sets_failed(self):
        """Test that rejecting a task sets status to FAILED."""
        from backend.app.db.models import TaskStatus
        from backend.app.workers.agent_runner import _resume_task_async

        mock_task = MagicMock()
        mock_task.status = TaskStatus.PLAN_REVIEW

        with (
            patch("backend.app.workers.agent_runner._create_worker_engine", AsyncMock()),
            patch("backend.app.workers.agent_runner.async_sessionmaker") as mock_factory,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_factory.return_value.return_value = mock_session

            with patch(
                "backend.app.workers.agent_runner._get_task", AsyncMock(return_value=mock_task)
            ):
                await _resume_task_async("task-id", approved=False)

                assert mock_task.status == TaskStatus.FAILED
                assert "rejected" in mock_task.error_message.lower()
