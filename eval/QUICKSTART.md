# Eval Harness Quick Start

## Prerequisites

1. Ensure database and Redis are running:
   ```bash
   docker-compose up -d postgres redis
   ```

2. Apply migrations:
   ```bash
   gravity db upgrade head
   ```

3. **Start the FastAPI server** (in a separate terminal):
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```

4. Register a test repository (in another terminal):
   ```bash
   gravity repo add /Users/oscarthieleserrano/code/personal_projects/test_agent --name "test_repo"
   ```

## Alternative: Direct Database Registration

If you prefer not to run the API server, you can register repos directly via Python:

```python
import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.app.db.models import Repository
from backend.app.config import settings

async def register_repo():
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = Repository(
            id=uuid4(),
            name="test_repo",
            path="/path/to/your/repo",
            description="Test repository for eval",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(repo)
        await session.commit()
        print(f"✅ Registered repo: {repo.name} ({repo.id})")

    await engine.dispose()

asyncio.run(register_repo())
```

Save this as `register_repo.py` and run: `python register_repo.py`

## Running Your First Experiment

### Step 1: Update Task Definitions

Edit `eval/tasks/*.yaml` files to use your actual repository IDs:

```yaml
# eval/tasks/01_streamlit_multi_page_app.yaml
id: "01_streamlit_multi_page_app"
repo_id: "test_repo"  # <-- Use the name you registered
description: |
  Your task description...
```

### Step 2: Run the Experiment

```bash
python -m eval.run_experiment eval/experiments/exp_phase1_baseline.yaml
```

### Step 3: View Results

Results are saved to:
- `eval/results/exp_phase1_baseline.json` (detailed)
- `eval/results/exp_phase1_baseline.csv` (spreadsheet-friendly)

## Example Output

```json
{
  "experiment_id": "exp_phase1_baseline",
  "description": "Phase 1 baseline...",
  "tasks": [
    {
      "experiment_id": "exp_phase1_baseline",
      "eval_task_id": "01_streamlit_multi_page_app",
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "tests_exit_code": 0,
      "files_changed_count": 4,
      "fix_attempts_count": 1,
      "duration_seconds": 120.5
    }
  ]
}
```

## Enabling LLM Judge

To enable dev-time LLM evaluation:

```yaml
# eval/experiments/exp_with_judge.yaml
experiment_id: "exp_with_judge"
use_judge: true  # <-- Enable judge
```

This adds judge scores to results:
```json
{
  "judge_overall": 8,
  "judge_recommendation": "accept"
}
```

## Creating Custom Tasks

1. Create a new YAML file in `eval/tasks/`:

```yaml
id: "my_custom_task"
repo_id: "my_repo"
description: |
  Detailed task description that will be passed
  to the Antigravity pipeline as user_request.
tags:
  - "backend"
  - "feature"
timeout_seconds: 900
```

2. Run experiment - it will automatically pick up new tasks.

## Troubleshooting

### "Connection refused" when running gravity commands
- **Solution**: Start the FastAPI server first:
  ```bash
  uvicorn backend.app.main:app --reload --port 8000
  ```
- **Alternative**: Use the direct database registration script above

### "Repository not found"
- Ensure `repo_id` in task YAML matches a registered repository
- Check registered repos:
  ```bash
  # Via API (requires server running)
  gravity repo list

  # Or query database directly
  psql -d antigravity -c "SELECT id, name, path FROM repositories;"
  ```

### Task times out
- Increase `timeout_seconds` in task YAML
- Check task status in database: `gravity task status <task_id>`

### No results generated
- Check logs for errors
- Ensure `eval/results/` directory exists and is writable

## Next Steps

- Compare results across experiments
- Analyze metrics trends (test pass rate, fix attempts, duration)
- Use judge scores to identify quality issues
- Iterate on agent prompts and configurations
