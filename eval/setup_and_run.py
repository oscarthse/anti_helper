"""
Automated Eval Setup and Execution

This script automates the complete eval workflow:
1. Creates test_agent repo directory structure
2. Registers repo in database
3. Runs all eval tasks
4. Collects and analyzes results
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.config import settings
from backend.app.db.models import Repository
from eval.run_experiment import ExperimentRunner

logger = structlog.get_logger(__name__)

TEST_AGENT_PATH = "/Users/oscarthieleserrano/code/personal_projects/test_agent"


async def setup_test_repo() -> str:
    """
    Create and register the test_agent repository.

    Returns:
        Repository name
    """
    logger.info("Setting up test repository")

    # Create directory if it doesn't exist
    test_path = Path(TEST_AGENT_PATH)
    test_path.mkdir(parents=True, exist_ok=True)

    # Create README
    readme = test_path / "README.md"
    if not readme.exists():
        readme.write_text("""# Test Agent Repository

This repository is used for automated evaluation of Antigravity Dev agents.
Each subdirectory contains a complete project built from scratch by the agents.

## Projects

Projects are created in subdirectories by the eval harness:
- `todo_api/` - REST API for todo list
- `weather_cli/` - Command-line weather app
- `blog_generator/` - Static blog generator
- `expense_tracker/` - Personal expense tracker
- `data_pipeline/` - ETL data processing pipeline

Each project is self-contained with its own dependencies and tests.
""")

    # Initialize git if not already
    if not (test_path / ".git").exists():
        subprocess.run(["git", "init"], cwd=test_path, check=True)
        subprocess.run(["git", "add", "README.md"], cwd=test_path, check=False)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=test_path,
            check=False,
        )

    # Register in database
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Check if already exists
        from sqlalchemy import select

        result = await session.execute(
            select(Repository).where(Repository.name == "test_agent")
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info("Repository already registered", repo_id=str(existing.id))
            await engine.dispose()
            return "test_agent"

        # Create new
        repo = Repository(
            id=uuid4(),
            name="test_agent",
            path=str(test_path),
            description="Automated eval test repository",
            project_type="multi",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(repo)
        await session.commit()

        logger.info(
            "Repository registered",
            repo_id=str(repo.id),
            name=repo.name,
            path=repo.path,
        )

    await engine.dispose()
    return "test_agent"


async def run_full_eval(experiment_config: str = "eval/experiments/exp_phase1_baseline.yaml"):
    """
    Run complete evaluation workflow.

    Args:
        experiment_config: Path to experiment config
    """
    logger.info("Starting automated eval workflow")

    # Step 1: Setup repo
    repo_name = await setup_test_repo()
    logger.info("Test repository ready", repo_name=repo_name)

    # Step 2: Run experiment
    logger.info("Running experiment", config=experiment_config)
    runner = ExperimentRunner(experiment_config)
    results = await runner.run()

    # Step 3: Print summary
    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)
    print(f"\nExperiment: {results.experiment_id}")
    print(f"Total Tasks: {len(results.tasks)}")

    completed = [t for t in results.tasks if t.status == "completed"]
    failed = [t for t in results.tasks if t.status == "failed"]

    print(f"Completed: {len(completed)}")
    print(f"Failed: {len(failed)}")

    print("\n" + "-" * 80)
    print("TASK RESULTS")
    print("-" * 80)

    for task in results.tasks:
        status_icon = "✅" if task.status == "completed" else "❌"
        print(f"\n{status_icon} {task.eval_task_id}")
        print(f"   Status: {task.status}")
        if task.duration_seconds:
            print(f"   Duration: {task.duration_seconds:.1f}s")
        if task.files_changed_count:
            print(f"   Files Changed: {task.files_changed_count}")
        if task.tests_exit_code is not None:
            test_status = "PASS" if task.tests_exit_code == 0 else "FAIL"
            print(f"   Tests: {test_status}")
        if task.error_message:
            print(f"   Error: {task.error_message[:100]}")

    print("\n" + "=" * 80)
    print(f"Results saved to: eval/results/{results.experiment_id}.json")
    print("=" * 80 + "\n")

    return results


async def main():
    """Main entry point."""
    import sys

    config = "eval/experiments/exp_phase1_baseline.yaml"
    if len(sys.argv) > 1:
        config = sys.argv[1]

    results = await run_full_eval(config)

    # Return exit code based on results
    failed_count = len([t for t in results.tasks if t.status == "failed"])
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
