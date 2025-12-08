
import asyncio
import os
import sys
from sqlalchemy import select
from uuid import UUID

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.db.session import get_session
from backend.app.db.models import Task, AgentLog

async def inspect():
    ids_to_check = [
        '1adb518e-7d5d-43cd-a275-c9375e237d3d', # seen in worker logs
        '521e5120-b4bd-4507-92d4-71a63aa42b0d'  # manually triggered
    ]

    async for session in get_session():
        print("--- Active Missions (EXECUTING) ---")
        stmt_executing = select(Task).where(Task.status == 'EXECUTING')
        res = await session.execute(stmt_executing)
        active_tasks = res.scalars().all()

        if not active_tasks:
            print("No tasks currently in EXECUTING state.")

        for t in active_tasks:
            print(f"[{t.status}] {t.title or t.user_request[:50]} (ID: {t.id})")
            print(f"  Current Agent: {t.current_agent}")
            print(f"  Current Step: {t.current_step}")

        print("\n--- Specific IDs Checked ---")
        for tid in ids_to_check:
            stmt = select(Task).where(Task.id == UUID(tid))
            res = await session.execute(stmt)
            task = res.scalar_one_or_none()
            if task:
                 print(f"ID {tid}:")
                 print(f"  Title: {task.title}")
                 print(f"  Request: {task.user_request}")
                 print(f"  Status: {task.status}")
                 print(f"  Current Agent: {task.current_agent}")
            else:
                 print(f"ID {tid}: NOT FOUND")

        return

if __name__ == "__main__":
    asyncio.run(inspect())
