"""
Unit Tests for Eval Schemas

Tests for Pydantic models used in eval harness.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from eval.schemas import (
    DevEvalScore,
    EvalTask,
    EvalTaskResult,
)


class TestEvalSchemas:
    """Tests for eval Pydantic schemas."""

    def test_eval_task_validation(self):
        """
        TEST: EvalTask validates required fields.

        CLAIM BEING TESTED:
        "EvalTask requires id, repo_id, and description"
        """
        # GIVEN: Valid task data
        data = {
            "id": "task_1",
            "repo_id": "repo_1",
            "description": "Test task",
            "tags": ["test"],
            "timeout_seconds": 600,
        }

        # WHEN: We validate the data
        task = EvalTask.model_validate(data)

        # THEN: Task should be created successfully
        assert task.id == "task_1"
        assert task.repo_id == "repo_1"
        assert task.description == "Test task"
        assert task.tags == ["test"]
        assert task.timeout_seconds == 600

    def test_eval_task_defaults(self):
        """
        TEST: EvalTask applies default values.

        CLAIM BEING TESTED:
        "EvalTask has sensible defaults for optional fields"
        """
        # GIVEN: Minimal task data
        data = {
            "id": "task_1",
            "repo_id": "repo_1",
            "description": "Test task",
        }

        # WHEN: We validate the data
        task = EvalTask.model_validate(data)

        # THEN: Defaults should be applied
        assert task.tags == []
        assert task.timeout_seconds == 900

    def test_dev_eval_score_range_validation(self):
        """
        TEST: DevEvalScore enforces 0-10 range.

        CLAIM BEING TESTED:
        "Score fields must be between 0 and 10"
        """
        # GIVEN: Valid scores
        valid_data = {
            "correctness": 8,
            "style_alignment": 7,
            "architectural_fit": 9,
            "safety_risks": 2,
            "overall": 8,
        }

        # WHEN: We validate
        score = DevEvalScore.model_validate(valid_data)

        # THEN: Should succeed
        assert score.correctness == 8
        assert score.overall == 8

        # GIVEN: Invalid score (out of range)
        invalid_data = {
            "correctness": 11,  # Too high
            "style_alignment": 7,
            "architectural_fit": 9,
            "safety_risks": 2,
            "overall": 8,
        }

        # WHEN/THEN: Should raise validation error
        with pytest.raises(ValidationError):
            DevEvalScore.model_validate(invalid_data)

    def test_eval_task_result_optional_fields(self):
        """
        TEST: EvalTaskResult handles optional fields.

        CLAIM BEING TESTED:
        "Result fields can be None for failed/incomplete tasks"
        """
        # GIVEN: Minimal result data
        data = {
            "experiment_id": "exp_1",
            "eval_task_id": "task_1",
            "status": "FAILED",
        }

        # WHEN: We validate
        result = EvalTaskResult.model_validate(data)

        # THEN: Optional fields should be None
        assert result.task_id is None
        assert result.tests_exit_code is None
        assert result.files_changed_count is None
        assert result.duration_seconds is None
        assert result.judge_overall is None
