"""
Evaluation Schemas

Pydantic models for eval tasks, experiments, and results.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvalTask(BaseModel):
    """Definition of a single evaluation task."""

    id: str
    repo_id: str
    description: str
    tags: list[str] = Field(default_factory=list)
    timeout_seconds: int = 900


class ExperimentConfig(BaseModel):
    """Configuration for an evaluation experiment."""

    experiment_id: str
    description: str
    use_judge: bool = True  # Judge is critical - enabled by default
    llm: dict[str, float] = Field(default_factory=dict)
    policies: dict[str, bool | int] = Field(default_factory=dict)


class DevEvalScore(BaseModel):
    """LLM judge scores (dev-time only)."""

    correctness: int = Field(ge=0, le=10)
    style_alignment: int = Field(ge=0, le=10)
    architectural_fit: int = Field(ge=0, le=10)
    safety_risks: int = Field(ge=0, le=10)
    overall: int = Field(ge=0, le=10)


class DevEvalResult(BaseModel):
    """LLM judge evaluation result (dev-time only)."""

    scores: DevEvalScore
    recommendation: Literal["accept", "needs_review", "reject"]
    key_issues: list[str] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)


class EvalTaskResult(BaseModel):
    """Result of running a single eval task."""

    experiment_id: str
    eval_task_id: str
    task_id: str | None = None
    status: str
    tests_exit_code: int | None = None
    files_changed_count: int | None = None
    fix_attempts_count: int | None = None
    tests_run_command: str | None = None
    duration_seconds: float | None = None
    # Judge evaluation (critical for quality assessment)
    judge_overall: int | None = None
    judge_correctness: int | None = None
    judge_style: int | None = None
    judge_architecture: int | None = None
    judge_safety: int | None = None
    judge_recommendation: str | None = None
    judge_key_issues: list[str] = Field(default_factory=list)
    judge_key_strengths: list[str] = Field(default_factory=list)
    error_message: str | None = None


class ExperimentResults(BaseModel):
    """Aggregated results for an experiment."""

    experiment_id: str
    description: str
    tasks: list[EvalTaskResult]
