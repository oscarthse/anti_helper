import asyncio
import sys
import os

# Add project root to python path
sys.path.append(os.getcwd())

from backend.app.workers.agent_runner import _run_task_async
import structlog

# Configure basic logging to stdout
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

async def debug_run():
    task_id = "06d3febf-3da5-42f2-aae1-0f5e612ca4fa"
    print(f"Starting inline debug of task {task_id}")

    try:
        await _run_task_async(task_id)
        print("Inline execution finished successfully")
    except Exception as e:
        print(f"Inline execution FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_run())
