"""
Unit Tests for GravityCore Schema (Pydantic Models)

Tests the Explainability Contract - all agent outputs must conform
to the defined Pydantic models with proper validation.
"""

# Add project paths
# Add project paths

import pytest
from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    ChangeSet,
    DocUpdateLog,
    ExecutionRun,
    TaskPlan,
    TaskStatus,
    TaskStep,
    ToolCall,
)
from pydantic import ValidationError


class TestAgentOutput:
    """Tests for the AgentOutput schema - the core Explainability Contract."""

    def test_valid_agent_output(self, sample_agent_output_data):
        """Test that valid data creates a proper AgentOutput."""
        output = AgentOutput(**sample_agent_output_data)

        assert output.ui_title == sample_agent_output_data["ui_title"]
        assert output.ui_subtitle == sample_agent_output_data["ui_subtitle"]
        assert output.confidence_score == 0.85
        assert output.agent_persona == AgentPersona.PLANNER
        assert len(output.tool_calls) == 1

    def test_missing_required_field_ui_title(self, sample_agent_output_data):
        """Test that missing ui_title raises ValidationError."""
        del sample_agent_output_data["ui_title"]

        with pytest.raises(ValidationError) as exc_info:
            AgentOutput(**sample_agent_output_data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ui_title",) for e in errors)

    def test_missing_required_field_ui_subtitle(self, sample_agent_output_data):
        """Test that missing ui_subtitle raises ValidationError."""
        del sample_agent_output_data["ui_subtitle"]

        with pytest.raises(ValidationError) as exc_info:
            AgentOutput(**sample_agent_output_data)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ui_subtitle",) for e in errors)

    def test_confidence_score_above_one(self, sample_agent_output_data):
        """Test that confidence_score > 1.0 raises ValidationError."""
        sample_agent_output_data["confidence_score"] = 1.5

        with pytest.raises(ValidationError) as exc_info:
            AgentOutput(**sample_agent_output_data)

        errors = exc_info.value.errors()
        assert any("confidence_score" in str(e) for e in errors)

    def test_confidence_score_below_zero(self, sample_agent_output_data):
        """Test that confidence_score < 0.0 raises ValidationError."""
        sample_agent_output_data["confidence_score"] = -0.1

        with pytest.raises(ValidationError) as exc_info:
            AgentOutput(**sample_agent_output_data)

        errors = exc_info.value.errors()
        assert any("confidence_score" in str(e) for e in errors)

    def test_requires_review_property(self, sample_agent_output_data):
        """Test that requires_review is True when confidence < 0.7."""
        sample_agent_output_data["confidence_score"] = 0.5
        output = AgentOutput(**sample_agent_output_data)

        assert output.requires_review is True

        sample_agent_output_data["confidence_score"] = 0.9
        output = AgentOutput(**sample_agent_output_data)

        assert output.requires_review is False

    def test_invalid_agent_persona(self, sample_agent_output_data):
        """Test that invalid agent_persona raises ValidationError."""
        sample_agent_output_data["agent_persona"] = "invalid_persona"

        with pytest.raises(ValidationError) as exc_info:
            AgentOutput(**sample_agent_output_data)

        errors = exc_info.value.errors()
        assert any("agent_persona" in str(e) for e in errors)

    def test_empty_tool_calls(self, sample_agent_output_data):
        """Test that empty tool_calls list is valid."""
        sample_agent_output_data["tool_calls"] = []
        output = AgentOutput(**sample_agent_output_data)

        assert output.tool_calls == []


class TestToolCall:
    """Tests for the ToolCall schema."""

    def test_valid_tool_call(self):
        """Test valid ToolCall creation."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/app/main.py"},
            result="file contents",
            success=True,
        )

        assert tool_call.tool_name == "read_file"
        assert tool_call.arguments == {"path": "/app/main.py"}
        assert tool_call.success is True
        assert tool_call.id is not None  # Auto-generated UUID

    def test_tool_call_with_error(self):
        """Test ToolCall with error."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/nonexistent"},
            success=False,
            error="FileNotFoundError: File not found",
        )

        assert tool_call.success is False
        assert "FileNotFoundError" in tool_call.error

    def test_tool_call_missing_tool_name(self):
        """Test that missing tool_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCall(arguments={"path": "/app"})

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("tool_name",) for e in errors)

    def test_tool_call_duration_ms(self):
        """Test ToolCall with duration tracking."""
        tool_call = ToolCall(
            tool_name="run_shell_command",
            arguments={"command": "ls"},
            result="output",
            success=True,
            duration_ms=150,
        )

        assert tool_call.duration_ms == 150


class TestTaskPlan:
    """Tests for the TaskPlan schema."""

    def test_valid_task_plan(self, sample_task_plan_data):
        """Test valid TaskPlan creation."""
        # Convert string persona to enum for steps
        for step in sample_task_plan_data["steps"]:
            step["agent_persona"] = AgentPersona(step["agent_persona"])

        plan = TaskPlan(**sample_task_plan_data)

        assert plan.summary == sample_task_plan_data["summary"]
        assert len(plan.steps) == 3
        assert plan.estimated_complexity == 4
        assert plan.total_steps == 3

    def test_task_plan_complexity_validation(self):
        """Test that complexity must be 1-10."""
        with pytest.raises(ValidationError):
            TaskPlan(
                summary="Test",
                steps=[],
                estimated_complexity=15,  # Invalid: > 10
            )

        with pytest.raises(ValidationError):
            TaskPlan(
                summary="Test",
                steps=[],
                estimated_complexity=0,  # Invalid: < 1
            )

    def test_task_plan_empty_steps(self):
        """Test that empty steps list is valid."""
        plan = TaskPlan(
            summary="Empty plan",
            steps=[],
            estimated_complexity=1,
        )

        assert plan.steps == []
        assert plan.total_steps == 0


class TestTaskStep:
    """Tests for the TaskStep schema."""

    def test_valid_task_step(self):
        """Test valid TaskStep creation."""
        step = TaskStep(
            order=1,
            description="Implement feature",
            agent_persona=AgentPersona.CODER_BE,
            dependencies=[],
            files_affected=["main.py"],
        )

        assert step.order == 1
        assert step.agent_persona == AgentPersona.CODER_BE

    def test_task_step_with_dependencies(self):
        """Test TaskStep with dependencies."""
        step = TaskStep(
            order=3,
            description="Run tests",
            agent_persona=AgentPersona.QA,
            dependencies=[1, 2],
        )

        assert step.dependencies == [1, 2]


class TestChangeSet:
    """Tests for the ChangeSet schema."""

    def test_valid_changeset(self):
        """Test valid ChangeSet creation."""
        changeset = ChangeSet(
            file_path="src/main.py",
            action="modify",
            diff="@@ -1,3 +1,5 @@\n+import logging",
            explanation="Added logging import",
            language="python",
        )

        assert changeset.file_path == "src/main.py"
        assert changeset.action == "modify"
        assert "logging" in changeset.diff

    def test_changeset_actions(self):
        """Test different changeset actions."""
        for action in ["create", "modify", "delete"]:
            changeset = ChangeSet(
                file_path="test.py",
                action=action,
                diff="diff content",
                explanation=f"Test {action}",
            )
            assert changeset.action == action


class TestExecutionRun:
    """Tests for the ExecutionRun schema."""

    def test_valid_execution_run(self):
        """Test valid ExecutionRun creation."""
        run = ExecutionRun(
            command="pytest",
            working_directory="/app",
            stdout="15 passed",
            stderr="",
            exit_code=0,
            duration_ms=5000,
        )

        assert run.success is True
        assert run.exit_code == 0
        assert run.duration_ms == 5000

    def test_failed_execution_run(self):
        """Test failed ExecutionRun."""
        run = ExecutionRun(
            command="pytest",
            working_directory="/app",
            stdout="",
            stderr="ImportError: No module named 'foo'",
            exit_code=1,
            duration_ms=100,
        )

        assert run.success is False
        assert "ImportError" in run.stderr

    def test_execution_run_output_property(self):
        """Test combined output property."""
        run = ExecutionRun(
            command="ls",
            working_directory="/app",
            stdout="file1.py\nfile2.py",
            stderr="warning: deprecated",
            exit_code=0,
            duration_ms=50,
        )

        output = run.output
        assert "STDOUT" in output
        assert "file1.py" in output
        assert "STDERR" in output
        assert "deprecated" in output


class TestDocUpdateLog:
    """Tests for the DocUpdateLog schema."""

    def test_valid_doc_update_log(self):
        """Test valid DocUpdateLog creation."""
        log = DocUpdateLog(
            files_updated=["README.md", "CHANGELOG.md"],
            changes=[
                ChangeSet(
                    file_path="README.md",
                    action="modify",
                    diff="+## New Feature",
                    explanation="Added new feature section",
                )
            ],
            summary="Updated documentation for new feature",
        )

        assert len(log.files_updated) == 2
        assert len(log.changes) == 1


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_status_values(self):
        """Test all TaskStatus enum values exist."""
        expected_statuses = [
            "pending",
            "planning",
            "plan_review",
            "executing",
            "testing",
            "documenting",
            "completed",
            "failed",
            "review_required",
        ]

        for status in expected_statuses:
            assert TaskStatus(status).value == status


class TestAgentPersona:
    """Tests for AgentPersona enum."""

    def test_all_persona_values(self):
        """Test all AgentPersona enum values exist."""
        expected_personas = [
            "planner",
            "coder_be",
            "coder_fe",
            "coder_infra",
            "qa",
            "docs",
        ]

        for persona in expected_personas:
            assert AgentPersona(persona).value == persona
