
import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.getcwd())

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings
from backend.app.db.models import Task, TaskStatus
from backend.app.workers.agent_runner import run_task

async def manual_approve(task_id: str):
    print(f"Connecting to DB to approve task {task_id}...")

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Get task
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            print("Task not found!")
            return

        print(f"Current status: {task.status}")

        # Update status
        task.status = TaskStatus.EXECUTING
        # task.updated_at = datetime.utcnow() # SQLAlchemy handles this

        await session.commit()
        print("Status updated to EXECUTING and committed.")

    await engine.dispose()

    # Queue worker
    print("Sending run_task message...")
    run_task.send(task_id)
    print("Message sent to worker.")

if __name__ == "__main__":
    task_id = "06d3febf-3da5-42f2-aae1-0f5e612ca4fa"
    asyncio.run(manual_approve(task_id))
