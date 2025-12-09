"""
Task and Experiment Loaders

Utilities for loading eval tasks and experiment configs from YAML files.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from eval.schemas import EvalTask, ExperimentConfig


def load_eval_tasks(tasks_dir: str | Path = "eval/tasks") -> list[EvalTask]:
    """
    Load all eval task definitions from YAML files.

    Args:
        tasks_dir: Directory containing *.yaml task definitions

    Returns:
        List of EvalTask objects
    """
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        return []

    tasks = []
    for yaml_file in sorted(tasks_path.glob("*.yaml")):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
            tasks.append(EvalTask.model_validate(data))

    return tasks


def load_experiment_config(config_path: str | Path) -> ExperimentConfig:
    """
    Load experiment configuration from YAML file.

    Args:
        config_path: Path to experiment config YAML

    Returns:
        ExperimentConfig object
    """
    with open(config_path) as f:
        data = yaml.safe_load(f)
        return ExperimentConfig.model_validate(data)
