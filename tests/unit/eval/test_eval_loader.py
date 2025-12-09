"""
Unit Tests for Eval Loader

Tests for loading eval tasks and experiment configs from YAML.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from eval.loader import load_eval_tasks, load_experiment_config


class TestEvalLoader:
    """Tests for eval task and experiment loading."""

    def test_load_eval_task_from_yaml(self):
        """
        TEST: Load eval task from YAML file.

        CLAIM BEING TESTED:
        "YAML task definitions are correctly parsed into EvalTask objects"
        """
        # GIVEN: A YAML file with task definition
        yaml_content = """
id: "test_task"
repo_id: "test_repo"
description: "Test task description"
tags:
  - "test"
  - "unit"
timeout_seconds: 600
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_file = Path(tmpdir) / "test_task.yaml"
            task_file.write_text(yaml_content)

            # WHEN: We load tasks from the directory
            tasks = load_eval_tasks(tmpdir)

            # THEN: Task should be loaded correctly
            assert len(tasks) == 1
            task = tasks[0]
            assert task.id == "test_task"
            assert task.repo_id == "test_repo"
            assert task.description == "Test task description"
            assert task.tags == ["test", "unit"]
            assert task.timeout_seconds == 600

    def test_load_experiment_config_from_yaml(self):
        """
        TEST: Load experiment config from YAML file.

        CLAIM BEING TESTED:
        "YAML experiment configs are correctly parsed into ExperimentConfig objects"
        """
        # GIVEN: A YAML file with experiment config
        yaml_content = """
experiment_id: "test_exp"
description: "Test experiment"
use_judge: true
llm:
  planner_temperature: 0.35
  coder_temperature: 0.25
policies:
  max_fix_attempts: 3
  linter_blocking: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            # WHEN: We load the config
            config = load_experiment_config(f.name)

            # THEN: Config should be loaded correctly
            assert config.experiment_id == "test_exp"
            assert config.description == "Test experiment"
            assert config.use_judge is True
            assert config.llm["planner_temperature"] == 0.35
            assert config.llm["coder_temperature"] == 0.25
            assert config.policies["max_fix_attempts"] == 3
            assert config.policies["linter_blocking"] is False

    def test_load_eval_tasks_empty_directory(self):
        """
        TEST: Loading from empty directory returns empty list.

        CLAIM BEING TESTED:
        "Empty task directory returns empty list without errors"
        """
        # GIVEN: An empty directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # WHEN: We load tasks
            tasks = load_eval_tasks(tmpdir)

            # THEN: Should return empty list
            assert tasks == []

    def test_load_eval_tasks_nonexistent_directory(self):
        """
        TEST: Loading from nonexistent directory returns empty list.

        CLAIM BEING TESTED:
        "Nonexistent task directory returns empty list without errors"
        """
        # GIVEN: A nonexistent directory path
        nonexistent = "/tmp/nonexistent_eval_tasks_dir_12345"

        # WHEN: We load tasks
        tasks = load_eval_tasks(nonexistent)

        # THEN: Should return empty list
        assert tasks == []
