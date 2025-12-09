import asyncio
import os
import sys
from uuid import UUID

import pytest
from sqlalchemy import update

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.db.models import Task, TaskStatus
from backend.app.db.session import get_session


@pytest.mark.skip(reason="Requires PostgreSQL database connection")
async def test_pause_resume():
    root_id = "1adb518e-7d5d-43cd-a275-c9375e237d3d"  # From previous inspection

    print(f"Testing PAUSE on Root Task {root_id}...")

    async for session in get_session():
        # PAUSE
        stmt = update(Task).where(Task.id == UUID(root_id)).values(status=TaskStatus.PAUSED)
        await session.execute(stmt)
        await session.commit()
        print("-> Set status to PAUSED. Check worker logs for 'workflow_paused'.")

        await asyncio.sleep(10)

        # RESUME
        print("Testing RESUME...")
        stmt = update(Task).where(Task.id == UUID(root_id)).values(status=TaskStatus.EXECUTING)
        await session.execute(stmt)
        await session.commit()
        print("-> Set status to EXECUTING. Worker should resume.")
        return


if __name__ == "__main__":
    asyncio.run(test_pause_resume())
