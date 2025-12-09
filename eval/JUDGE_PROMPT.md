# LLM Judge Prompt

This document shows the exact prompt used by the eval harness judge to evaluate agent-generated code.

## Key Changes

**Before**: Judge only saw task description and metrics (test exit code, files changed count, fix attempts)

**After**: Judge now sees:
- Task description
- Execution metrics
- **Actual code changes** (diffs from CODER agents)
- **Test output** (stdout/stderr from QA agent)
- **List of files changed**

## Full Prompt Template

```
You are a senior staff software engineer evaluating code changes made by an AI agent.

Your job is to review the changes and produce a STRICT, STRUCTURED JSON evaluation.
Do NOT be polite. Be honest and critical.

-----------------------------
CONTEXT
-----------------------------

## Task Request
{task_description}

## Execution Metrics
- Test Status: {test_status}  # e.g. "PASSED (exit code: 0)" or "FAILED (exit code: 1)"
- Files Changed: [{files_list}]  # e.g. ["app/main.py", "app/pages/Overview.py"]
- Fix Attempts: {fix_attempts}

## Code Changes
{code_changes}  # Diffs from CODER agents (truncated to ~500 chars per file, max 10 files)

## Test Output
{test_output}  # stdout (1000 chars) + stderr (500 chars) from QA agent

-----------------------------
EVALUATION INSTRUCTIONS
-----------------------------

You must evaluate the change along the following dimensions, each scored 0–10:

1. Correctness
   - 0 = clearly incorrect or breaks tests.
   - 10 = clearly correct and complete for the described task.
   - IMPORTANT:
     - If tests FAILED (non-zero exit code), correctness MUST be in the 0–3 range.
     - If tests PASSED, you may still reduce correctness if you see obvious logic flaws, but explain why.

2. Style Alignment
   - 0 = totally inconsistent, messy, ignores common best practices.
   - 10 = clean, idiomatic, and consistent with what you can infer from the surrounding code.

3. Architectural Fit
   - 0 = violates obvious layering/architecture, introduces god objects, or hacks around existing patterns.
   - 10 = clearly respects and extends existing architecture and abstractions.

4. Safety Risks
   - 0 = no obvious safety concerns.
   - 10 = extremely risky (e.g. auth bypass, injection, data loss, unsafe filesystem/network behavior).
   - A higher number means **more** risk.

5. Overall
   - Holistic score, not a simple average.
   - Priority order: Correctness > Safety > Architectural Fit > Style.
   - Rough guide:
     - 0–3: bad / should be rejected.
     - 4–6: mixed / works partially but needs significant review.
     - 7–8: acceptable but with some issues.
     - 9–10: very strong for this context.

Recommendation:
- "accept"        → Good enough to merge with only light review.
- "needs_review"  → Functionally plausible but requires careful human review.
- "reject"        → Not acceptable in current form (major correctness/safety/architecture problems).

-----------------------------
OUTPUT FORMAT (IMPORTANT)
-----------------------------

You MUST respond with a single JSON object matching exactly this schema:

{
  "scores": {
    "correctness": int,          // 0-10
    "style_alignment": int,      // 0-10
    "architectural_fit": int,    // 0-10
    "safety_risks": int,         // 0-10, higher = more risky
    "overall": int               // 0-10
  },
  "recommendation": "accept" | "needs_review" | "reject",
  "key_issues": [
    "short bullet point about the most important problem",
    "another short bullet point"
  ],
  "key_strengths": [
    "short bullet point about the main strength",
    "another short bullet point"
  ]
}

Rules:
- RETURN ONLY JSON. No prose before or after.
- Be concise in key_issues / key_strengths (1–4 items each).
- If tests FAILED, clearly mention this in key_issues.
```

## Data Sources

The judge receives data from:

1. **Task Model**: `user_request`, `tests_exit_code`, `fix_attempts_count`
2. **AgentRun (CODER)**: `technical_reasoning` contains ChangeSet with file diffs
3. **AgentRun (QA)**: `technical_reasoning` contains ExecutionRun with test stdout/stderr

## Truncation Strategy

To keep token usage reasonable:
- **Code changes**: First 500 chars per file, max 10 files
- **Test output**: First 1000 chars stdout + 500 chars stderr

This provides enough context for meaningful evaluation without excessive costs.

## Example Judge Output

```json
{
  "scores": {
    "correctness": 8,
    "style_alignment": 7,
    "architectural_fit": 9,
    "safety_risks": 2,
    "overall": 8
  },
  "recommendation": "accept",
  "key_issues": [
    "Missing input validation on user_id parameter",
    "Error handling could be more specific"
  ],
  "key_strengths": [
    "Clean separation of concerns with service layer",
    "Comprehensive test coverage including edge cases",
    "Proper async/await usage throughout"
  ]
}
```

## Usage

The judge is **optional** and controlled by experiment config:

```yaml
# eval/experiments/exp_with_judge.yaml
experiment_id: "exp_with_judge"
use_judge: true  # Enable LLM evaluation
```

When enabled, judge scores are added to `EvalTaskResult`:
- `judge_overall`: Overall score (0-10)
- `judge_recommendation`: accept / needs_review / reject
