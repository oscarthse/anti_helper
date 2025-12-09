# Eval Harness - Command Reference

## Quick Commands

### Run Everything (Recommended)
```bash
# Start services
docker-compose up -d postgres redis

# Run automated eval
python -m eval.setup_and_run

# Analyze results
python -m eval.analyze_results eval/results/exp_phase1_baseline.json
```

### With LLM Judge
```bash
python -m eval.setup_and_run eval/experiments/exp_with_judge.yaml
```

## Individual Steps

### Setup Only
```bash
python -c "from eval.setup_and_run import setup_test_repo; import asyncio; asyncio.run(setup_test_repo())"
```

### Run Experiment Only
```bash
python -m eval.run_experiment eval/experiments/exp_phase1_baseline.yaml
```

### Analyze Only
```bash
python -m eval.analyze_results eval/results/exp_phase1_baseline.json
```

## Check Status

### List Registered Repos
```bash
# Via API (requires server running)
gravity repo list

# Via database
psql -d antigravity -c "SELECT id, name, path FROM repositories;"
```

### Check Task Status
```bash
gravity task status <task_id>
```

### View Results
```bash
# JSON (detailed)
cat eval/results/exp_phase1_baseline.json | jq

# CSV (spreadsheet)
open eval/results/exp_phase1_baseline.csv
```

## Cleanup

### Reset Test Repo
```bash
cd /Users/oscarthieleserrano/code/personal_projects/test_agent
git reset --hard HEAD
git clean -fd
```

### Remove Old Results
```bash
rm -rf eval/results/*
```

## Development

### Run Tests
```bash
pytest tests/unit/eval/ -v
```

### Check Imports
```bash
python -c "from eval.loader import load_eval_tasks; print(f'Found {len(load_eval_tasks(\"eval/tasks\"))} tasks')"
```

## Troubleshooting

### Connection Refused
```bash
# Start API server
uvicorn backend.app.main:app --reload --port 8000
```

### Database Issues
```bash
# Check connection
psql -d antigravity -c "SELECT 1;"

# Run migrations
gravity db upgrade head
```

### Redis Issues
```bash
# Check Redis
redis-cli ping

# Restart Redis
docker-compose restart redis
```

## File Locations

- **Tasks**: `eval/tasks/*.yaml`
- **Experiments**: `eval/experiments/*.yaml`
- **Results**: `eval/results/*.json` and `*.csv`
- **Test Repo**: `/Users/oscarthieleserrano/code/personal_projects/test_agent`
- **Logs**: Check terminal output or `backend/logs/`
