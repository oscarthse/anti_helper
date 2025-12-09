"""
Experiment Runner

Main script for running evaluation experiments.
Usage: python -m eval.run_experiment eval/experiments/exp_phase1_baseline.yaml
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings
from backend.app.db.models import AgentRun, Repository, Task, TaskStatus
from backend.app.workers.agent_runner import run_task
from eval.judge import EvalJudge
from eval.loader import load_eval_tasks, load_experiment_config
from eval.schemas import EvalTaskResult, ExperimentResults

logger = structlog.get_logger(__name__)


class ExperimentRunner:
    """Runs evaluation experiments using existing Antigravity pipeline."""

    def __init__(self, experiment_config_path: str):
        """
        Initialize experiment runner.

        Args:
            experiment_config_path: Path to experiment YAML config
        """
        self.config = load_experiment_config(experiment_config_path)
        self.eval_tasks = load_eval_tasks()
        self.results: list[EvalTaskResult] = []
        self.judge = EvalJudge() if self.config.use_judge else None

    async def run(self) -> ExperimentResults:
        """
        Run the complete experiment.

        Returns:
            ExperimentResults with all task results
        """
        logger.info(
            "experiment_started",
            experiment_id=self.config.experiment_id,
            num_tasks=len(self.eval_tasks),
            use_judge=self.config.use_judge,
        )

        engine = await self._create_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            for eval_task in self.eval_tasks:
                result = await self._run_eval_task(eval_task, session_factory)
                self.results.append(result)

            # Save results
            await self._save_results()

            return ExperimentResults(
                experiment_id=self.config.experiment_id,
                description=self.config.description,
                tasks=self.results,
            )

        finally:
            await engine.dispose()

    async def _run_eval_task(
        self,
        eval_task,
        session_factory,
    ) -> EvalTaskResult:
        """
        Run a single eval task through the Antigravity pipeline.

        Args:
            eval_task: EvalTask definition
            session_factory: SQLAlchemy session factory

        Returns:
            EvalTaskResult with metrics
        """
        logger.info("eval_task_started", eval_task_id=eval_task.id)

        async with session_factory() as session:
            # Get repository
            repo = await self._get_repository(session, eval_task.repo_id)
            if not repo:
                return EvalTaskResult(
                    experiment_id=self.config.experiment_id,
                    eval_task_id=eval_task.id,
                    status="FAILED",
                    error_message=f"Repository {eval_task.repo_id} not found",
                )

            # Create task
            task = Task(
                repo_id=repo.id,
                user_request=eval_task.description,
                title=f"Eval: {eval_task.id}",
                status=TaskStatus.PENDING,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            task_id = str(task.id)
            logger.info("eval_task_created", eval_task_id=eval_task.id, task_id=task_id)

        # Execute task via Dramatiq (existing pipeline)
        # NOTE: In a real scenario, we'd enqueue via dramatiq.
        # For simplicity, we call the async function directly.
        try:
            from backend.app.workers.agent_runner import _run_task_async

            await asyncio.wait_for(
                _run_task_async(task_id),
                timeout=eval_task.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("eval_task_timeout", eval_task_id=eval_task.id, task_id=task_id)

        # Collect metrics
        async with session_factory() as session:
            task = await self._get_task(session, UUID(task_id))
            if not task:
                return EvalTaskResult(
                    experiment_id=self.config.experiment_id,
                    eval_task_id=eval_task.id,
                    task_id=task_id,
                    status="UNKNOWN",
                    error_message="Task not found after execution",
                )

            duration = None
            if task.completed_at and task.created_at:
                duration = (task.completed_at - task.created_at).total_seconds()

            result = EvalTaskResult(
                experiment_id=self.config.experiment_id,
                eval_task_id=eval_task.id,
                task_id=task_id,
                status=task.status.value,
                tests_exit_code=task.tests_exit_code,
                files_changed_count=task.files_changed_count,
                fix_attempts_count=task.fix_attempts_count,
                tests_run_command=task.tests_run_command,
                duration_seconds=duration,
                error_message=task.error_message,
            )

            # Optional judge evaluation
            if self.judge and task.status == TaskStatus.COMPLETED:
                # Gather code changes and test output
                code_changes = await self._get_code_changes(session, task.id)
                test_output = await self._get_test_output(session, task.id)
                files_changed_list = await self._get_files_changed_list(session, task.id)

                judge_result = await self.judge.evaluate_task(
                    task_description=task.user_request,
                    test_exit_code=task.tests_exit_code,
                    files_changed=files_changed_list,
                    fix_attempts=task.fix_attempts_count or 0,
                    code_changes=code_changes,
                    test_output=test_output,
                )
                if judge_result:
                    # Store all judge scores for comprehensive analysis
                    result.judge_overall = judge_result.scores.overall
                    result.judge_correctness = judge_result.scores.correctness
                    result.judge_style = judge_result.scores.style_alignment
                    result.judge_architecture = judge_result.scores.architectural_fit
                    result.judge_safety = judge_result.scores.safety_risks
                    result.judge_recommendation = judge_result.recommendation
                    result.judge_key_issues = judge_result.key_issues
                    result.judge_key_strengths = judge_result.key_strengths

            logger.info(
                "eval_task_completed",
                eval_task_id=eval_task.id,
                task_id=task_id,
                status=result.status,
                judge_overall=result.judge_overall,
                judge_recommendation=result.judge_recommendation,
            )

            return result

    async def _save_results(self) -> None:
        """Save experiment results to JSON and CSV."""
        results_dir = Path("eval/results")
        results_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = results_dir / f"{self.config.experiment_id}.json"
        experiment_results = ExperimentResults(
            experiment_id=self.config.experiment_id,
            description=self.config.description,
            tasks=self.results,
        )
        with open(json_path, "w") as f:
            json.dump(experiment_results.model_dump(), f, indent=2)

        logger.info("results_saved_json", path=str(json_path))

        # Save CSV
        csv_path = results_dir / f"{self.config.experiment_id}.csv"
        with open(csv_path, "w", newline="") as f:
            if self.results:
                writer = csv.DictWriter(f, fieldnames=self.results[0].model_dump().keys())
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result.model_dump())

        logger.info("results_saved_csv", path=str(csv_path))

    async def _create_engine(self):
        """Create async engine for database access."""
        return create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

    async def _get_repository(self, session: AsyncSession, repo_id: str) -> Repository | None:
        """Get repository by ID or name."""
        # Try UUID first
        try:
            uuid_id = UUID(repo_id)
            result = await session.execute(select(Repository).where(Repository.id == uuid_id))
            return result.scalar_one_or_none()
        except ValueError:
            pass

        # Try by name
        result = await session.execute(select(Repository).where(Repository.name == repo_id))
        return result.scalar_one_or_none()

    async def _get_task(self, session: AsyncSession, task_id: UUID) -> Task | None:
        """Get task by ID."""
        result = await session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def _get_code_changes(self, session: AsyncSession, task_id: UUID) -> str:
        """Extract code changes from CODER agent runs."""
        result = await session.execute(
            select(AgentRun)
            .where(AgentRun.task_id == task_id)
            .where(AgentRun.agent_persona.in_(["CODER_BE", "CODER_FE", "CODER_INFRA"]))
            .order_by(AgentRun.created_at)
        )
        agent_runs = result.scalars().all()

        changes = []
        for run in agent_runs:
            if run.technical_reasoning:
                try:
                    reasoning = json.loads(run.technical_reasoning)
                    if "changes" in reasoning:
                        for change in reasoning["changes"]:
                            file_path = change.get("file_path", "unknown")
                            diff = change.get("diff", "")
                            changes.append(f"File: {file_path}\n{diff[:500]}")
                except json.JSONDecodeError:
                    pass

        return "\n\n".join(changes[:10]) if changes else "(No code changes captured)"

    async def _get_test_output(self, session: AsyncSession, task_id: UUID) -> str:
        """Extract test output from QA agent runs."""
        result = await session.execute(
            select(AgentRun)
            .where(AgentRun.task_id == task_id)
            .where(AgentRun.agent_persona == "QA")
            .order_by(AgentRun.created_at.desc())
        )
        qa_run = result.scalars().first()

        if qa_run and qa_run.technical_reasoning:
            try:
                reasoning = json.loads(qa_run.technical_reasoning)
                stdout = reasoning.get("stdout", "")
                stderr = reasoning.get("stderr", "")
                output = f"STDOUT:\n{stdout[:1000]}\n\nSTDERR:\n{stderr[:500]}"
                return output
            except json.JSONDecodeError:
                pass

        return "(No test output captured)"

    async def _get_files_changed_list(self, session: AsyncSession, task_id: UUID) -> list[str]:
        """Extract list of changed file paths."""
        result = await session.execute(
            select(AgentRun)
            .where(AgentRun.task_id == task_id)
            .where(AgentRun.agent_persona.in_(["CODER_BE", "CODER_FE", "CODER_INFRA"]))
        )
        agent_runs = result.scalars().all()

        files = set()
        for run in agent_runs:
            if run.technical_reasoning:
                try:
                    reasoning = json.loads(run.technical_reasoning)
                    if "changes" in reasoning:
                        for change in reasoning["changes"]:
                            file_path = change.get("file_path")
                            if file_path:
                                files.add(file_path)
                except json.JSONDecodeError:
                    pass

        return sorted(files)


async def main(config_path: str) -> None:
    """
    Main entry point for experiment runner.

    Args:
        config_path: Path to experiment config YAML
    """
    runner = ExperimentRunner(config_path)
    results = await runner.run()

    logger.info(
        "experiment_complete",
        experiment_id=results.experiment_id,
        total_tasks=len(results.tasks),
        completed=[t for t in results.tasks if t.status == "completed"],
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m eval.run_experiment <experiment_config.yaml>")
        sys.exit(1)

    config_path = sys.argv[1]
    asyncio.run(main(config_path))
