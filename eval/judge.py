"""
LLM Judge (Dev-Time Only)

Optional LLM-based evaluation of task results.
Uses existing LLMClient to score completed tasks.
"""

from __future__ import annotations

import structlog

from gravity_core.llm import LLMClient
from eval.schemas import DevEvalResult

logger = structlog.get_logger(__name__)


class EvalJudge:
    """LLM judge for evaluating task results (dev-time only)."""

    def __init__(self, llm_client: LLMClient | None = None):
        """
        Initialize judge with LLM client.

        Args:
            llm_client: LLMClient instance (created if not provided)
        """
        self.llm_client = llm_client or LLMClient()

    async def evaluate_task(
        self,
        task_description: str,
        test_exit_code: int | None,
        files_changed: list[str],
        fix_attempts: int,
        code_changes: str = "",
        test_output: str = "",
    ) -> DevEvalResult | None:
        """
        Evaluate a completed task using LLM judge.

        Args:
            task_description: Original task request
            test_exit_code: Exit code from tests (0 = pass)
            files_changed: List of file paths modified
            fix_attempts: Number of QA fix attempts
            code_changes: Diffs or code snippets (truncated if needed)
            test_output: Test execution output (truncated if needed)

        Returns:
            DevEvalResult or None if evaluation fails
        """
        prompt = self._build_judge_prompt(
            task_description=task_description,
            test_exit_code=test_exit_code,
            files_changed=files_changed,
            fix_attempts=fix_attempts,
            code_changes=code_changes,
            test_output=test_output,
        )

        try:
            result = await self.llm_client.generate_structured_output(
                prompt=prompt,
                output_schema=DevEvalResult,
                model_name="gpt-4o",
                temperature=0.1,  # Low temp for consistent, strict evaluation
            )
            return result
        except Exception as e:
            logger.warning(
                "judge_evaluation_failed",
                error=str(e),
                task_description=task_description[:50],
            )
            return None

    def _build_judge_prompt(
        self,
        task_description: str,
        test_exit_code: int | None,
        files_changed: list[str],
        fix_attempts: int,
        code_changes: str,
        test_output: str,
    ) -> str:
        """Build evaluation prompt for LLM judge."""
        test_status = (
            f"PASSED (exit code: {test_exit_code})"
            if test_exit_code == 0
            else f"FAILED (exit code: {test_exit_code})"
        )
        files_list = ", ".join(f'"{f}"' for f in files_changed) if files_changed else "none"

        return f"""You are a senior staff software engineer evaluating code changes made by an AI agent.

Your job is to review the changes and produce a STRICT, STRUCTURED JSON evaluation.
Do NOT be polite. Be honest and critical. This is a quality gate.

-----------------------------
CONTEXT
-----------------------------

## Task Request
{task_description}

## Execution Metrics
- Test Status: {test_status}
- Files Changed: [{files_list}]
- Fix Attempts: {fix_attempts}

## Code Changes
{code_changes or "(No code changes captured)"}

## Test Output
{test_output or "(No test output captured)"}

-----------------------------
EVALUATION INSTRUCTIONS
-----------------------------

You must evaluate the change along the following dimensions, each scored 0–10:

1. Correctness (HIGHEST PRIORITY)
   - 0 = clearly incorrect or breaks tests.
   - 10 = clearly correct and complete for the described task.
   - CRITICAL RULES:
     - If tests FAILED (non-zero exit code), correctness MUST be 0–3.
     - If tests PASSED but logic is flawed, reduce score and explain.
     - Check: Does it fully satisfy the task requirements?
     - Check: Are edge cases handled?
     - Check: Is error handling present?

2. Style Alignment
   - 0 = totally inconsistent, messy, ignores common best practices.
   - 10 = clean, idiomatic, and consistent with what you can infer from the surrounding code.
   - Check: Type hints present and correct?
   - Check: Docstrings for classes/functions?
   - Check: Follows PEP 8 / language conventions?
   - Check: No placeholder code (pass, ..., TODO, NotImplementedError)?
   - Check: Meaningful variable names?

3. Architectural Fit
   - 0 = violates obvious layering/architecture, introduces god objects, or hacks around existing patterns.
   - 10 = clearly respects and extends existing architecture and abstractions.
   - Check: Proper separation of concerns?
   - Check: Follows existing patterns (async/await, error handling, logging)?
   - Check: No circular dependencies or tight coupling?
   - Check: Appropriate abstraction level?

4. Safety Risks (SECOND HIGHEST PRIORITY)
   - 0 = no obvious safety concerns.
   - 10 = extremely risky (e.g. auth bypass, injection, data loss, unsafe filesystem/network behavior).
   - A higher number means **more** risk.
   - Check: SQL injection vulnerabilities?
   - Check: Path traversal risks?
   - Check: Unsafe eval/exec usage?
   - Check: Missing input validation?
   - Check: Secrets hardcoded or exposed?
   - Check: Unsafe file operations?

5. Overall
   - Holistic score, not a simple average.
   - Priority order: Correctness > Safety > Architectural Fit > Style.
   - Scoring guide:
     - 0–3: Reject - major problems, not acceptable.
     - 4–6: Needs Review - works partially but significant issues.
     - 7–8: Accept with caveats - acceptable but has issues.
     - 9–10: Strong - production-ready quality.

Recommendation:
- "accept"        → Production-ready, merge with light review.
- "needs_review"  → Functionally works but requires careful human review before merge.
- "reject"        → Not acceptable - major correctness/safety/architecture problems.

-----------------------------
OUTPUT FORMAT (IMPORTANT)
-----------------------------

You MUST respond with a single JSON object matching exactly this schema:

{{
  "scores": {{
    "correctness": int,          // 0-10
    "style_alignment": int,      // 0-10
    "architectural_fit": int,    // 0-10
    "safety_risks": int,         // 0-10, higher = more risky
    "overall": int               // 0-10
  }},
  "recommendation": "accept" | "needs_review" | "reject",
  "key_issues": [
    "Specific problem with code location if possible",
    "Another concrete issue"
  ],
  "key_strengths": [
    "Specific positive aspect",
    "Another strength"
  ]
}}

Rules:
- RETURN ONLY JSON. No prose before or after.
- Be concise in key_issues / key_strengths (1–4 items each).
- Be SPECIFIC in issues - mention file names, patterns, or code smells.
- If tests FAILED, clearly mention this in key_issues.
- If safety_risks > 3, MUST include specific vulnerability in key_issues.
- If correctness < 7, MUST explain what's incomplete/wrong in key_issues."""
