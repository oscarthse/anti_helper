# Evaluation Harness

**Dev-time only** evaluation framework for running automated experiments on Antigravity Dev.

## Overview

This evaluation harness allows you to:
- Run a fixed set of eval tasks that build complete projects from scratch
- **LLM judge evaluates all code changes** (reads diffs, test output, scores quality)
- Collect automatic metrics (test results, files changed, fix attempts, duration)
- Analyze results with **judge scores as primary signal**
- Generate actionable recommendations for improving agent performance
- Save results in JSON and CSV formats

## Quick Start (Fully Automated)

The easiest way to run evaluations:

```bash
# 1. Ensure services are running
docker-compose up -d postgres redis

# 2. Run automated eval (creates repo, runs tasks, analyzes results)
python -m eval.setup_and_run
```

This will:
- Create `/Users/oscarthieleserrano/code/personal_projects/test_agent` directory
- Register it in the database
- Run all 5 eval tasks (each builds a complete project from scratch)
- Save results to `eval/results/`
- Print summary report

## Eval Tasks (From-Scratch Projects)

All tasks build complete, working projects in subdirectories:

1. **todo_api** - REST API with FastAPI, SQLAlchemy, tests
2. **weather_cli** - CLI app with Click/Typer, API integration
3. **blog_generator** - Static site generator with Jinja2
4. **expense_tracker** - Flask web app with database
5. **data_pipeline** - ETL pipeline with pandas, validation

Each project includes:
- Complete source code
- requirements.txt
- README.md with setup instructions
- Unit tests
- Proper error handling

## Analyzing Results

After running experiments, analyze performance:

```bash
python -m eval.analyze_results eval/results/exp_phase1_baseline.json
```

This generates a report with:
- **🎯 Judge Evaluation (PRIMARY SIGNAL)**
  - Accept rate (target: 70%+)
  - Quality scores: correctness, style, architecture, safety
  - Key issues and strengths identified by judge
- Success/failure patterns
- Performance metrics
- **Actionable recommendations** prioritized by judge feedback:
  - Prompt improvements
  - Autonomy adjustments
  - Reflection enhancements
  - Workflow changes
  - Tool usage suggestions

## Manual Workflow

If you prefer manual control:

### 1. Setup Repository

```bash
# Create directory
mkdir -p /Users/oscarthieleserrano/code/personal_projects/test_agent
cd /Users/oscarthieleserrano/code/personal_projects/test_agent
git init

# Register in database (requires API server running)
gravity repo add . --name "test_agent"
```

### 2. Run Experiment

```bash
python -m eval.run_experiment eval/experiments/exp_phase1_baseline.yaml
```

### 3. Analyze Results

```bash
python -m eval.analyze_results eval/results/exp_phase1_baseline.json
```

## Directory Structure

```
eval/
├── tasks/                         # 5 from-scratch project tasks
│   ├── 01_todo_api.yaml
│   ├── 02_weather_cli.yaml
│   ├── 03_blog_generator.yaml
│   ├── 04_expense_tracker.yaml
│   └── 05_data_pipeline.yaml
├── experiments/                   # Experiment configs
│   ├── exp_phase1_baseline.yaml
│   └── exp_with_judge.yaml
├── results/                       # Generated results (gitignored)
├── setup_and_run.py              # Automated workflow
├── analyze_results.py            # Performance analysis
├── run_experiment.py             # Main runner
├── judge.py                      # Optional LLM judge
├── loader.py                     # YAML loaders
└── schemas.py                    # Pydantic models
```

## Results Format

### JSON Output

```json
{
  "experiment_id": "exp_phase1_baseline",
  "tasks": [
    {
      "eval_task_id": "01_todo_api",
      "status": "completed",
      "tests_exit_code": 0,
      "files_changed_count": 8,
      "fix_attempts_count": 1,
      "duration_seconds": 245.3,
      "judge_overall": 8,
      "judge_correctness": 9,
      "judge_style": 7,
      "judge_architecture": 8,
      "judge_safety": 1,
      "judge_recommendation": "accept",
      "judge_key_issues": ["Missing input validation"],
      "judge_key_strengths": ["Clean architecture", "Good test coverage"]
    }
  ]
}
```

### Analysis Report

```
📊 SUMMARY
Total Tasks: 5
Success Rate: 80.0%
Avg Duration: 312.5s
Avg Files Changed: 7.2
Avg Fix Attempts: 1.4

🎯 JUDGE EVALUATION (CRITICAL)
Tasks Judged: 5
Accept Rate: 60.0% (3 accepted, 2 need review, 0 rejected)

Average Scores (0-10):
  Overall Quality: 7.2
  Correctness: 8.4
  Style: 6.8
  Architecture: 7.6
  Safety Risk: 1.4 (lower is better)

💡 RECOMMENDATIONS

🎯 Prompt Improvements:
  • ⚠️  Accept rate 60% below target - refine agent prompts
  • Quality score 7.2/10 - emphasize best practices in prompts
  • Emphasize test-driven development in coder prompt

🔍 Reflection Enhancements:
  • Add 'verify_requirements_met' step before marking complete
  • Add self-reflection step after code generation

⚙️  Workflow Changes:
  • Add pre-flight validation step before code generation
  • Include progress checkpoints for long-running tasks
```

## Performance Improvement Areas

The analyzer identifies opportunities in:

Recommendations are **prioritized by judge feedback**:

### 1. Judge-Driven (Highest Priority)
- **Accept rate < 70%** → Major prompt refinement
- **Correctness < 7** → Task completion issues
- **Safety > 3** → Security vulnerabilities
- **Overall < 6** → Quality gates needed

### 2. Prompt Engineering
- Task decomposition clarity
- Explicit requirements
- Example patterns
- Error handling guidance

### 3. Autonomy Levels
- When to ask for human review
- Parallel vs sequential execution
- Retry strategies
- Escalation thresholds

### 4. Reflection Mechanisms
- Self-checking before submission
- Learning from previous attempts
- Quality validation gates
- Test-first approaches

### 5. Workflow Optimization
- Pre-flight checks
- Incremental validation
- Progress tracking
- Timeout handling

### 6. Tool Usage
- New tool opportunities
- Tool sequencing
- Error recovery tools
- Validation tools

## Experiment Configs

### Standard Configuration
```yaml
experiment_id: "exp_phase1_baseline"
use_judge: true  # Judge is critical - enabled by default
llm:
  planner_temperature: 0.35
  coder_temperature: 0.25
```

### Quick Iteration (Judge Disabled)
```yaml
experiment_id: "exp_quick_test"
use_judge: false  # Only for rapid testing - not recommended
```

## Creating Custom Tasks

```yaml
id: "my_project"
repo_id: "test_agent"
description: |
  Build a complete [project type] in the 'my_project' subdirectory.
  
  Requirements:
  - Create my_project/ directory
  - [Specific requirements]
  - Include requirements.txt
  - Add README.md
  - Write tests
tags:
  - "category"
timeout_seconds: 1200
```

## Limitations

### By Design (Minimal Scope)

1. **No Automatic Repo Reset** - Manually reset between runs if needed
2. **Config Not Auto-Applied** - Experiment config loaded but not injected into agents
3. **Direct Execution** - Bypasses Dramatiq queue for simplicity
4. **No Diff Capture** - Git diffs not automatically stored

All limitations are documented with rationale and workarounds.

## Safety

- **Dev-time only** - No production impact
- **Gitignored results** - Not committed to repo
- **Existing pipeline** - Uses proven execution path
- **Judge-first evaluation** - LLM judge provides critical quality assessment

## Next Steps

1. **Run baseline experiment** - Get judge scores for current agents
2. **Analyze results** - Focus on accept rate and judge feedback
3. **Identify critical issues** - Prioritize low correctness/safety scores
4. **Iterate on prompts** - Target specific judge recommendations
5. **Compare experiments** - Track accept rate improvements
6. **Aim for 80%+ accept rate** - Production-ready quality threshold

The goal is to systematically improve agent performance through **judge-driven insights**.

## Judge Evaluation Details

See [JUDGE_IMPORTANCE.md](JUDGE_IMPORTANCE.md) for:
- Why judge is the primary quality signal
- What data judge receives (code diffs, test output)
- How judge scores are weighted in analysis
- Cost considerations (~$0.01-0.02 per task)
