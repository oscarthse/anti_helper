import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select

from backend.app.db.models import Task
from backend.app.db.session import get_session, init_db


async def check():
    print("Initializing DB...")
    try:
        await init_db()
        print("DB Initialized.")
    except Exception as e:
        print(f"DB Init Failed: {e}")
        return

    print("Checking Session...")
    async for session in get_session():
        try:
            result = await session.execute(select(Task).limit(1))
            tasks = result.scalars().all()
            print(f"Query Success. Tasks found: {len(tasks)}")
        except Exception as e:
            print(f"Query Failed: {e}")
        break


if __name__ == "__main__":
    asyncio.run(check())
