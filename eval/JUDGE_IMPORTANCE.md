# Judge-Centric Evaluation System

The LLM judge is now the **PRIMARY quality signal** in the eval harness. All analysis and recommendations prioritize judge scores over automatic metrics.

## Key Changes

### 1. Judge Enabled by Default
- `use_judge: true` in all experiment configs
- Judge evaluation is now standard, not optional
- Temperature lowered to 0.1 for strict, consistent evaluation

### 2. Comprehensive Judge Data Collection
Judge now receives:
- ✅ Task description
- ✅ Test exit code and execution metrics
- ✅ **Actual code changes** (diffs from CODER agents, ~500 chars per file)
- ✅ **Test output** (stdout/stderr from QA agent, ~1500 chars total)
- ✅ **List of files changed**

### 3. Full Judge Scores Stored
`EvalTaskResult` now captures:
- `judge_overall` - Holistic quality (0-10)
- `judge_correctness` - Task completion (0-10)
- `judge_style` - Code quality (0-10)
- `judge_architecture` - Design fit (0-10)
- `judge_safety` - Security risks (0-10, higher = worse)
- `judge_recommendation` - accept / needs_review / reject
- `judge_key_issues` - Critical problems identified
- `judge_key_strengths` - What worked well

### 4. Judge-First Analysis

The analyzer now prioritizes judge metrics:

#### Primary Signal: Accept Rate
```
< 50% accept rate → 🚨 CRITICAL: Major prompt overhaul needed
< 70% accept rate → ⚠️  Refine agent prompts
≥ 70% accept rate → ✅ Good quality
```

#### Secondary Signals:
- **Overall Quality < 6/10** → Add quality gates
- **Correctness < 7/10** → 🚨 Agents not completing tasks properly
- **Safety > 3/10** → 🚨 Security issues detected

### 5. Judge-Driven Recommendations

Recommendations are now ordered by impact:

1. **Judge-based** (highest priority)
   - Accept rate issues
   - Correctness problems
   - Security concerns
   - Quality thresholds

2. **Metric-based** (secondary)
   - Test pass rates
   - Fix attempts
   - Duration
   - Success rates

## Example Output

```
📊 SUMMARY
Total Tasks: 5
Success Rate: 100.0%
Avg Duration: 312.5s

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
  • Low style scores - add code quality examples to coder prompt

🔍 Reflection Enhancements:
  • Add 'verify_requirements_met' step before marking complete
  • Implement style checking before submission
```

## Judge Prompt (Strict Evaluation)

The judge uses a **critical, no-nonsense** prompt:

```
You are a senior staff software engineer evaluating code changes made by an AI agent.

Your job is to review the changes and produce a STRICT, STRUCTURED JSON evaluation.
Do NOT be polite. Be honest and critical.
```

Key evaluation rules:
- **Failed tests → Correctness MUST be 0-3**
- **Priority order: Correctness > Safety > Architecture > Style**
- **Scoring guide:**
  - 0-3: Bad / should be rejected
  - 4-6: Mixed / needs significant review
  - 7-8: Acceptable with some issues
  - 9-10: Very strong

## Why Judge is Critical

### Automatic Metrics Miss:
- ❌ Code quality and style
- ❌ Architectural fit
- ❌ Security vulnerabilities
- ❌ Maintainability issues
- ❌ Best practice violations

### Judge Catches:
- ✅ Logic errors that pass tests
- ✅ Security anti-patterns
- ✅ Poor design choices
- ✅ Style inconsistencies
- ✅ Missing error handling

## Cost Considerations

Judge adds ~2-3K tokens per task:
- Prompt: ~1K tokens
- Code changes: ~500-1K tokens
- Test output: ~300-500 tokens
- Response: ~200-300 tokens

**Cost per task**: ~$0.01-0.02 with GPT-4o

For 5 tasks: **~$0.05-0.10 per experiment**

This is negligible compared to the value of accurate quality assessment.

## Usage

Judge is now automatic:

```bash
# Judge runs by default
python -m eval.setup_and_run

# Analysis prioritizes judge scores
python -m eval.analyze_results eval/results/exp_phase1_baseline.json
```

To disable judge (not recommended):

```yaml
# eval/experiments/custom.yaml
use_judge: false  # Only for quick iterations
```

## Next Steps

1. **Run baseline with judge** - Get quality scores for current agents
2. **Identify top issues** - Focus on low accept rate / correctness
3. **Iterate on prompts** - Target specific judge feedback
4. **Compare experiments** - Track accept rate improvements
5. **Aim for 80%+ accept rate** - Production-ready quality threshold
