# DEEP ARCHITECTURAL AUDIT & MIGRATION STRATEGY

## I. CRITICAL LOGIC FAILURES (The "Bug Report")

### 1. The "Hallucinated Success" Loop
*   **Severity: HIGH**
*   **Location:** `libs/gravity_core/agents/coder.py` (`_process_tool_call`)
*   **Logical Flaw:** The agent assumes a coding step is successful solely because the `edit_file_snippet` tool returned `success=True`. This only confirms *File I/O success*, not *Semantic Correctness*.
*   **Risk:** The agent can write syntactically invalid Python code (e.g., indentation errors, missing colons), report "Success", and move to the next step. The subsequent step will fail confusingly, or worse, the user gets broken code.

### 2. Dependency Blindness
*   **Severity: HIGH**
*   **Location:** `libs/gravity_core/agents/coder.py`
*   **Logical Flaw:** The `CoderAgent` modifies source code files (e.g., adding `import numpy`) but has zero awareness of `pyproject.toml`, `requirements.txt`, or `package.json`.
*   **Risk:** The code works in the LLM's head but crashes immediately in runtime due to `ModuleNotFoundError`. The agent does not attempt to install missing dependencies.

### 3. The "Zombie State" Risk
*   **Severity: MED**
*   **Location:** `backend/app/db/models.py` (`TaskStatus`) & `backend/app/workers/agent_runner.py`
*   **Logical Flaw:** There is no "Heartbeat" or "Lease" mechanism for tasks in `TaskStatus.EXECUTING`.
*   **Risk:** If the Worker process crashes (OOM, restart) while a task is `EXECUTING`, the task remains in `EXECUTING` forever. The system waits indefinitely for a worker that is already dead.

### 4. Context Window Pollution
*   **Severity: MED**
*   **Location:** `libs/gravity_core/base.py` (`_tool_calls`)
*   **Logical Flaw:** The `BaseAgent` appends *every* tool call result to `self._tool_calls` and feeds it back into the context.
*   **Risk:** In long and complex tasks (e.g., refactoring 20 files), the tool output history will exceed the token limit, causing the agent to "forget" its original system prompt or the plan summary.

## II. THE ONTOLOGICAL MAP (Current Data Flow)

### Current Input Vector
User Prompt -> `PlannerAgent` -> `Task.task_plan` (JSON List) -> `CoderAgent` (Linear Loop) -> `Task.status=COMPLETED`

### The Breakpoint
**The Linear Fallacy:** The current system models software engineering as a linear list of steps (`current_step` integer).
*   **Failure Mode:** If Step 3 (Backend API) changes a data model, Step 5 (Frontend Form) *must* know about it. Currently, Step 5 only sees the original plan. It has no "live" view of the changes made in Step 3 unless it explicitly searches for them (which is probabilistic).
*   **Result:** Frontend/Backend drift. The frontend mocks data that no longer matches the backend schema.

## III. THE NEURO-SYMBOLIC INTEGRATION PLAN

### 1. The Blackboard Schema (Replacing Linear Lists)
We will introduce a **Graph-Based Blackboard** stored in PostgreSQL.

```sql
-- New entities for the Blackboard
CREATE TABLE knowledge_nodes (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    key VARCHAR(255) NOT NULL, -- e.g., "UserSchema", "API_Endpoint_Login"
    value JSONB NOT NULL,      -- The actual structured data (AST representation)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE dependency_edges (
    source_node_id UUID REFERENCES knowledge_nodes(id),
    target_node_id UUID REFERENCES knowledge_nodes(id),
    relationship_type VARCHAR(50) -- "imports", "calls", "defines"
);
```
**Benefit:** Agents read/write to the Blackboard. If `UserSchema` changes, any node dependent on it is marked "dirty".

### 2. The Symbolic Interceptor (Middleware)
We will inject a **Validation Layer** inside `ToolRegistry.execute`:

```python
# Pseudo-code for Interceptor
async def execute(tool_name, **kwargs):
    # 1. Pre-computation check
    if tool_name == "edit_file_snippet":
        code = kwargs['new_code']
        file_path = kwargs['file_path']

        # SYMBOLIC GUARDRAIL: AST Parse
        if file_path.endswith('.py'):
            try:
                ast.parse(code)
            except SyntaxError as e:
                return Failure(f"Refused to write invalid Python: {e}")

        # SYMBOLIC GUARDRAIL: Dependency Check
        imports = parse_imports(code)
        missing = check_dependencies(imports)
        if missing:
             return Failure(f"Refused code with missing deps: {missing}")

    # 2. Execute original tool checks
    return await original_execute(tool_name, **kwargs)
```

## IV. EXECUTION STRATEGY

### 1. Immediate Refactor (The "Triage")
Before building the full Blackboard, we must plug the biggest holes:
1.  **Add AST Validation:** Create a `GravityLinter` utility that `CoderAgent` usage *before* committing edits.
2.  **Add Heartbeats:** Add `last_heartbeat` to `Tasks` table and a background sweeper to reset dead tasks to `FAILED`.
3.  **Fix Context:** Implement a "Summarized Memory" window that keeps only the last N steps + the Plan Summary.

### 2. The Migration Path to "God Mode"
1.  **Phase A (Middleware):** Implement the `SymbolicInterceptor` to catch syntax/dep errors.
2.  **Phase B (State):** Migrate from `task_plan` (JSON) to `knowledge_nodes` (Table).
3.  **Phase C (The Brain):** Upgrade `PlannerAgent` to generate Dependency Graphs instead of Ordered Lists.
