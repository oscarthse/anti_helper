
import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.workers.agent_runner import run_task

def requeue(task_id):
    print(f"Re-enqueuing task {task_id}...")
    run_task.send(task_id)
    print("Done. Worker should pick it up.")

if __name__ == "__main__":
    task_id = "06d3febf-3da5-42f2-aae1-0f5e612ca4fa"
    requeue(task_id)
