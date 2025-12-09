import asyncio
import os
import sys
import time

# Add project root to path
sys.path.append(os.getcwd())

import logging

from sqlalchemy import select

from backend.app.db import AgentLog, Repository, Task, TaskStatus, get_session
from backend.app.workers.agent_runner import run_task

# Silence SQL logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROMPT = "Develop a multi-page Streamlit app for analyzing and explaining Apple stock data."
REPO_NAME = "test_agent"


async def run_evaluation():
    print(f"🔎 Starting Evaluation for request: '{PROMPT}'")

    async for session in get_session():
        # 1. Find Repository
        result = await session.execute(select(Repository).where(Repository.name == REPO_NAME))
        repo = result.scalar_one_or_none()

        if not repo:
            print(f"❌ Repository '{REPO_NAME}' not found. Please create it first.")
            return

        print(f"✅ Found repository: {repo.name} ({repo.path})")

        # 2. Create Task
        task = Task(
            repo_id=repo.id,
            user_request=PROMPT,
            title="Stock Analysis App Evaluation",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        print(f"✅ Task created: {task.id}")

        # 3. Dispatch to Worker
        print("🚀 Dispatching to worker...")
        run_task.send(str(task.id))

        # 4. Monitor Execution
        print("⏳ Waiting for agents to complete (this may take a minute)...")
        start_time = time.time()

        while True:
            await session.refresh(task)
            print(f"   Status: {task.status} | Step: {task.current_step}", end="\r")

            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                print(f"\n🏁 Finished with status: {task.status}")
                break

            if time.time() - start_time > 300:  # 5 min timeout
                print("\n❌ Timeout waiting for task completion")
                return

            await asyncio.sleep(2)

        # 5. Evaluate Output
        print("\n📊 --- EVALUATION REPORT ---")

        # Files Created
        files_count = task.files_changed_count or 0
        print(f"📁 Files Created/Modified: {files_count}")

        # Check actual files on disk
        # Scan repo path for streamlit app structure
        repo_path = repo.path
        found_files = []
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith(".py"):
                    found_files.append(os.path.join(root, file))

        print(f"📜 Python Files in Repo ({len(found_files)}):")
        for f in found_files:
            rel_path = os.path.relpath(f, repo_path)
            print(f"   - {rel_path}")

        # Fix Attempts
        print(f"🔧 Fix Attempts: {task.fix_attempts_count}")

        # Agent Reasoning (Grab Planner log)
        log_result = await session.execute(
            select(AgentLog).where(AgentLog.task_id == task.id, AgentLog.agent_persona == "planner")
        )
        planner_log = log_result.scalars().first()
        if planner_log:
            print(f"🧠 Plan Strategy: {planner_log.technical_reasoning[:200]}...")

        # Quality Check
        if files_count <= 1:
            print(
                "\n⚠️  CRITICAL QUALITY ISSUE: Only 1 file created. Multi-page apps require pages/ directory."
            )
        else:
            print("\n✅ Structure looks better (multiple files detected).")

        # Test Results
        print(f"🧪 Tests Run: {task.tests_run_command}")
        print(f"🏁 Test Exit Code: {task.tests_exit_code}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
