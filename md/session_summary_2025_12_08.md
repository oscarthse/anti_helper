# Session Report: Agent Quality & Execution Fixes
**Date**: December 8, 2025
**Status**: Critical Execution Validation Completed

## 1. Executive Summary
Today we resolved the "Hallucination Loop" where agents claimed to write code and pass tests without actually doing so. The system now:
1.  **Persists Code**: Files are guaranteed to be written to disk.
2.  **Tracks Changes**: The UI accurately reflects file creation/modification events.
3.  **Truthful QA**: The QA agent no longer lies about passing tests that didn't run.
4.  **Resilient Execution**: The worker process handles timezone-aware DB timestamps and restart signals correctly.

---

## 2. Technical Implementations (What We Fixed)

### A. Code Persistence & Change Tracking (The "Gaslighting" Fix)
*   **Problem**: Agents wrote code, but the `_changes` list wasn't populated if the tool result object structure wasn't exactly as expected, causing the UI to show "No changes required".
*   **Fix**: Modified `libs/gravity_core/agents/coder.py`:
    *   Added explicit `logger.info("create_new_module_success")` and `logger.info("edit_file_success")`.
    *   Added defensive logic to **always** append to `self._changes` list if the tool call was successful, ensuring the UI gets the "Code Updated" event.
    *   Verified `utils/manipulation.py` correctly handles `create_new_module` with recursive `__init__.py` creation up to safe boundaries.

### B. QA Agent Honesty
*   **Problem**: QA Agent reported `exit_code: 0` from `pytest` as "All Tests Passed", even when `pytest` said "collected 0 items".
*   **Fix**: Updated `libs/gravity_core/agents/qa.py`:
    *   Implemented regex parsing of `pytest` stdout.
    *   Now detects keywords: `no tests collected`, `collected 0 items`.
    *   **New State**: Returns `⚠️ No Tests Executed` status instead of False Positive success.

### C. Planner & Execution Logic
*   **Problem**: Tasks hung in `DOCUMENTING` or failed because `DocsAgent` tried to create files (which it can't do).
*   **Fix**:
    *   Updated `libs/gravity_core/agents/planner.py` System Prompt.
    *   **Rule Enforced**: "NEW file creation (including READMEs) must be assigned to `coder_infra` or `coder_be`. `docs` agent deals with EXISTING files only."
    *   Result: The final `test_agent` run successfully dispatched the README creation to `coder_infra`, which created the file.

### D. System Stability
*   **Problem**: Worker crashed with `NameError: 'UTC' is not defined`.
*   **Fix**: Updated `backend/app/workers/agent_runner.py` to use `datetime.utcnow()` (timezone naive) to match the PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` schema, preventing crashes during task completion.

---

## 3. Current State & Verification
We verified the system end-to-end with the `test_agent` repository:
*   ✅ **Repo Created**: `app.py`, `config.py`, `data_fetcher.py`, `README.md` exist on disk.
*   ✅ **Logs**: "Code Updated" events appear in the DB and UI.
*   ✅ **Honesty**: QA reported "No Tests Executed" (Correct).

---

## 4. Remaining Issues & Roadmap (For Tomorrow)

### High Priority
1.  **Force Test Creation**:
    *   *Current*: QA correctly reports "No tests".
    *   *Need*: Logic to **react** to that report. If "No tests executed", the system should auto-trigger a `Write Tests` step (Coder) before trying QA again.

2.  **DocsAgent Capabilities**:
    *   *Current*: DocsAgent fails if asked to create a new file.
    *   *Need*: Either give `DocsAgent` the `create_new_module` tool OR strictly enforce the Planner prompt (current solution). Long term, giving it creation rights is safer.

3.  **UI Repository Tree Sync**:
    *   *Current*: We assume the UI works because files are on disk.
    *   *Need*: Validating that the frontend `FileTree` component strictly mirrors specific `[NEW]` and `[DELETE]` events from the backend in real-time without needing a refresh.

4.  **Sandbox Isolation (Future)**:
    *   *Current*: Agents run tools directly on the host filesystem (safe for now, but not "anti-gravity").
    *   *Need*: Moving execution fully into the `sandbox` container defined in `docker-compose.yml` to prevent accidents on the user's machine.

### Functionalities to Add
*   **"Fix It" Loop**: When QA fails (or finds no tests), automatically spawn a child task to fix the code or write tests, rather than just marking the step as "failed" or "completed with warnings".
*   **Artifact/File Preview**: Allow the user to click a "Code Updated" log in the UI and see the split-diff of exactly what changed.

---
**Summary for Next Session**:
Start by implementing the **"No Tests -> Write Tests"** feedback loop. This bridges the gap between "Honest Reporting" and "Autonomous Improvement".
