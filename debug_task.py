import asyncio
import sys
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add backend to path
import sys
import os
sys.path.append(os.getcwd())

from backend.app.config import settings
from backend.app.db.models import Task, AgentLog

async def inspect():
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    task_id = "06d3febf-3da5-42f2-aae1-0f5e612ca4fa"

    async with async_session() as session:
        print(f"--- Inspecting Task {task_id} ---")
        result = await session.execute(select(Task).where(Task.id == UUID(task_id)))
        task = result.scalar_one_or_none()

        if task:
            print(f"Status: {task.status}")
            print(f"Current Agent: {task.current_agent}")
            print(f"Current Step: {task.current_step}")
            print(f"Error Message: {task.error_message}")
            print(f"Created: {task.created_at}")
            print(f"Updated: {task.updated_at}")
        else:
            print("Task not found.")

        print("\n--- Recent Logs ---")
        logs = await session.execute(
            select(AgentLog)
            .where(AgentLog.task_id == UUID(task_id))
            .order_by(AgentLog.created_at.desc())
            .limit(5)
        )
        for log in logs.scalars():
             print(f"[{log.created_at}] {log.agent_persona}: {log.ui_title}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect())
