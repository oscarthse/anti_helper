# Eval Harness Implementation Notes

## What Was Implemented

A minimal, well-contained evaluation harness that integrates with the existing Antigravity Dev architecture without requiring core changes.

### Core Components

1. **Schemas** (`eval/schemas.py`)
   - `EvalTask`: Task definition from YAML
   - `ExperimentConfig`: Experiment configuration
   - `EvalTaskResult`: Metrics collected per task
   - `DevEvalScore` / `DevEvalResult`: Optional LLM judge output

2. **Loaders** (`eval/loader.py`)
   - `load_eval_tasks()`: Discovers and parses task YAMLs
   - `load_experiment_config()`: Parses experiment config

3. **Judge** (`eval/judge.py`)
   - `EvalJudge`: Optional LLM-based evaluation (dev-time only)
   - Uses existing `LLMClient` for structured output

4. **Runner** (`eval/run_experiment.py`)
   - `ExperimentRunner`: Main orchestration class
   - Creates tasks via existing `Task` model
   - Executes via `_run_task_async()` (existing pipeline)
   - Collects metrics from database
   - Saves results to JSON/CSV

### Example Content

- **5 eval tasks** in `eval/tasks/`:
  - Streamlit multi-page app
  - API endpoint validation
  - Auth service refactoring
  - Redis caching layer
  - Memory leak fix

- **2 experiment configs** in `eval/experiments/`:
  - Baseline (no judge)
  - With judge enabled

### Tests

- **8 unit tests** in `tests/unit/eval/`:
  - YAML loading
  - Schema validation
  - Default values
  - Error handling

All tests pass ✅

## Integration Points

### Uses Existing Code

1. **Database**: Uses existing `Task`, `Repository`, `TaskStatus` models
2. **Execution**: Calls `_run_task_async()` from `agent_runner.py`
3. **Session**: Uses existing `async_sessionmaker` pattern
4. **LLM**: Uses existing `LLMClient` for judge
5. **Config**: Uses existing `settings` from `backend.app.config`

### No Core Changes Required

- No modifications to agent logic
- No changes to task execution pipeline
- No database schema changes
- No API endpoint changes

## Limitations (By Design)

### 1. No Automatic Repo Reset

**Why**: Git operations are complex and repo-specific. Implementing safe, universal reset logic would require:
- Understanding each repo's branching strategy
- Handling uncommitted changes
- Managing stashes and conflicts

**Workaround**: Manually reset repos between runs:
```bash
cd /path/to/repo
git reset --hard HEAD
git clean -fd
```

### 2. Config Not Auto-Applied

**Why**: Agent initialization happens deep in the execution pipeline. Injecting config would require:
- Modifying agent constructors
- Passing config through multiple layers
- Potentially breaking existing behavior

**Current State**: Config is loaded and stored but not applied to agents.

**Future Enhancement**: Add environment variable injection or agent factory pattern.

### 3. Direct Execution (Not via Dramatiq)

**Why**: Calling `_run_task_async()` directly is simpler for eval and avoids:
- Queue management complexity
- Worker process coordination
- Message broker dependencies

**Trade-off**: Bypasses queue system but ensures synchronous execution for metrics collection.

### 4. No Diff Capture

**Why**: Git diff capture requires:
- Knowing the baseline commit
- Handling merge conflicts
- Storing potentially large diffs

**Workaround**: Manually inspect repos after runs or use `git diff` commands.

## Design Decisions

### Minimal Scope

Deliberately kept minimal to avoid:
- Invasive architecture changes
- Breaking existing functionality
- Creating maintenance burden

### Reuse Over Reinvent

Used existing patterns:
- SQLAlchemy async sessions
- Pydantic models
- Structlog logging
- Existing LLMClient

### Dev-Time Only

Clearly marked as dev-time tool:
- Results gitignored
- No production dependencies
- Optional judge feature
- Separate directory structure

## Future Enhancements

Potential improvements (not implemented to keep scope minimal):

1. **Parallel Execution**: Run multiple tasks concurrently
2. **Result Comparison**: Compare metrics across experiments
3. **Web UI**: View results in browser
4. **Automatic Reset**: Safe repo reset with git
5. **Config Injection**: Apply experiment config to agents
6. **Diff Storage**: Capture and store git diffs
7. **Metrics Dashboard**: Visualize trends over time
8. **Failure Analysis**: Automatic categorization of failures

## Usage Patterns

### Basic Workflow

```bash
# 1. Register repos
gravity repo add /path/to/repo --name "my_repo"

# 2. Update task YAMLs with repo IDs
vim eval/tasks/01_*.yaml

# 3. Run experiment
python -m eval.run_experiment eval/experiments/exp_phase1_baseline.yaml

# 4. Analyze results
cat eval/results/exp_phase1_baseline.json
```

### With Judge

```bash
# Use experiment config with judge enabled
python -m eval.run_experiment eval/experiments/exp_with_judge.yaml
```

### Custom Experiments

```bash
# Create new experiment config
cat > eval/experiments/my_experiment.yaml << EOF
experiment_id: "my_experiment"
description: "Testing new configuration"
use_judge: true
llm:
  coder_temperature: 0.1  # More deterministic
EOF

# Run it
python -m eval.run_experiment eval/experiments/my_experiment.yaml
```

## Testing

Run eval harness tests:
```bash
pytest tests/unit/eval/ -v
```

All 8 tests pass:
- ✅ YAML loading
- ✅ Schema validation
- ✅ Default values
- ✅ Error handling

## Safety

- **No production impact**: Completely isolated from production code
- **Gitignored results**: Results not committed to repo
- **Existing pipeline**: Uses proven execution path
- **Optional judge**: LLM judge is opt-in only

## Summary

This eval harness provides a **minimal, safe, well-tested** foundation for running automated experiments on Antigravity Dev. It integrates cleanly with existing architecture and can be extended as needed without requiring core changes.
