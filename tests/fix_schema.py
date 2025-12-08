
import asyncio
import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.db.session import engine

async def fix_schema():
    print("Fixing Schema...")
    async with engine.begin() as conn:
        # 1. Add missing columns to tasks
        print("Adding columns...")
        await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_task_id UUID REFERENCES tasks(id);"))
        await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS definition_of_done JSONB;"))
        await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;"))
        await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP;"))

        # 2. Update TaskStatus Enum
        # Postgres requires running this inside a transaction usually, but sometimes outside?
        # "ALTER TYPE ... ADD VALUE" cannot run inside a transaction block in some versions,
        # but asyncpg/sqlalchemy might handle it.
        # Actually, "ALTER TYPE ... ADD VALUE" *cannot* run inside a transaction block.
        # We might need to run it with isolation_level="AUTOCOMMIT".
        print("Columns added.")

    # 3. Handle ENUM update separately
    # We need a separate connection with autocommit for ALTER TYPE
    print("Updating Enum...")
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            await conn.execute(text("ALTER TYPE taskstatus ADD VALUE 'PAUSED';"))
            print("Enum updated.")
        except Exception as e:
            if "duplicate key" in str(e) or "already exists" in str(e):
                print("Enum value 'PAUSED' already exists.")
            else:
                print(f"Enum update warning (might already exist): {e}")

if __name__ == "__main__":
    asyncio.run(fix_schema())
