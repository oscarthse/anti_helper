# Project Antigravity: The Master Plan & Architectural Vision

**Date:** December 8, 2025
**Version:** 1.0
**Status:** Foundation Validated / Scaling Phase

---

## 🏗 The Core Philosophy: Abstraction Ascension

**"Trust is the currency of autonomy."**

Our architectural thesis is simple: You cannot build a skyscraper on crumbling bricks. Most AI agents fail because they try to be "Magic High-Level Abstractions" (do it all) while their "Lowest-Level Abstractions" (tools, logging, honesty) are flawed.

Our strategy is **Abstraction Ascension**:
1.  **Level 0: The Foolproof Foundation (Trust)** - *We are here.*
2.  **Level 1: The Reactive Middleware (Resilience)** - *Next.*
3.  **Level 2: The God-Mode UI (Control)** - *The Goal.*

---

## 🏛 Level 0: The Foundation (Foolproof Execution)
*Achievements from Session 2025-12-08*

Before an agent can "build an app," it must be able to "write a file without lying." We have now solved the critical trust issues.

### 1. The "Gaslighting" Solution (Persistence Guarantee)
*   **The Problem**: standard LLM tool calls are "fire and forget." If the tool silently fails or the agent imagines a response, the user is gaslit.
*   **The Fix**:
    *   **Hardened Tool Wrappers**: Tools now return structured objects with explicit `success`, `error`, and `diff` fields.
    *   **Defensive Logging**: The Coder agent refuses to report success unless the underlying OS call confirms the write operation.
    *   *Result*: If the UI says "File Created," it exists on the execution volume. Period.

### 2. Radical Honesty (QA & Reporting)
*   **The Problem**: AI naturally pleases the user. It sees `exit_code: 0` from an empty test run and says "All Tests Passed!"
*   **The Fix**:
    *   **Semantic Output Parsing**: The QA agent now parses stdout for semantic truth (e.g., "collected 0 items"), not just exit codes.
    *   *Result*: The agent now reports "⚠️ No Tests Executed" instead of a false positive.

---

## ⚙️ Level 1: The Reactive Middleware (Intelligent loops)
*Technical Roadmap for the Backend*

Now that individual blocks are solid, we must cement them together into intelligent loops. A single straight-line execution (`Plan -> Code -> Test`) is brittle. We need **Cycles**.

### 1. The "Fix-It" Loop (Self-Correction)
Currently, if QA fails, the task marks as "Completed with Errors."
**Proposal**:
*   Instead of stopping, a `QA_FAILURE` event should trigger a **Child Task**.
*   **Logic**: `if (tests_failed) { spawn_task(type="fix_bug", context=error_logs) }`
*   *Implementation*: Refactor `AgentRunner` to support recursive task spawning. This turns the agent from a linear executor into a recursive problem solver.

### 2. The "Pre-computation" Loop (Proactive Thought)
*   **Concept**: The agent should verify its environment *before* acting.
*   **Implementation**:
    *   Before `write_code`, run `check_dependencies`.
    *   If missing, run `install_deps`.
    *   Only then run `write_code`.
*   This removes the "ImportError" class of failures completely.

---

## 🖥 Level 2: The God-Mode UI (The Interface)
*User Experience Vision*

The ultimate abstraction is where the user operates at the level of **Intent**, not Implementation. The UI should reflect this power.

### 1. The "Time-Machine" History
*   **Missing Feature**: Project-grouped History.
*   **Vision**:
    *   A left-sidebar organizing tasks by **Repository** -> **Session** -> **Task**.
    *   "Replay" capability: Click any past task to see the exact file state at that moment (using Git commit integration).
    *   *Why*: Debugging the agent's thought process requires seeing what IT saw yesterday.

### 2. User Preferences & "Soul"
*   **Missing Feature**: The agent doesn't know *me*.
*   **Vision**: `UserPreferences` Table.
    *   `preferred_language`: "Python"
    *   `testing_framework`: "pytest"
    *   `style_strictness`: "High" (runs mypy --strict)
    *   `personality`: "Concise" vs "Educational"
*   **Implementation**: These are injected into the System Prompt at runtime (`planner.py`).

### 3. The "Brain" Visualization
*   **Concept**: We rely on the `ProjectMap` (RAG) for context. The user is blind to it.
*   **Vision**: A visual graph node view in the UI showing:
    *   **Central Node**: Current Task.
    *   **Connected Nodes**: The files the agent "fetched" into its context window.
    *   *Why*: If the agent hallucinates, you can look at the Brain View and say "Oh, it didn't fetch `config.py`."

---

## 🚀 Execution Plan (Immediate Next Steps)

1.  **Refactor Task Engine for Recursion**:
    *   Update `tasks` table to support `parent_task_id`.
    *   Allow Agents to return a `NewTask` object instead of just text.

2.  **Implement "No Tests" Handler**:
    *   Hard-code logic in `AgentRunner`: If QA returns `No Tests Executed`, force transition to `Coder` with instruction "Write Unit Tests".

3.  **UI Settings Page**:
    *   Create `/settings` route.
    *   Build `UserPreferences` schema.
    *   Wire into `PlannerAgent`.

4.  **Visualize the Truth**:
    *   Add a "File Browser" tab to the War Room that shows the *actual* live container file system, verifying our "Level 0" foundation to the user in real-time.

---
**Final Thought**: We have moved from "Magic" (unreliable) to "Mechanics" (reliable). Now we build the Machine.
