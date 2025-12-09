# Project Structure

## Directory Organization

```
antigravity-dev/
├── libs/gravity_core/          # THE BRAIN - Intelligence & Skillset
├── backend/                    # THE BODY - State Manager & Dispatcher
├── frontend/                   # THE FACE - Visual Renderer
├── tests/                      # Test suites (unit, integration, e2e)
├── scripts/                    # Standalone utilities
├── md/                         # Technical documentation
└── docker-compose.yml          # Infrastructure orchestration
```

## Core Components

### 1. GravityCore (libs/gravity_core/)

**Purpose**: Pure intelligence layer containing agent personas, LLM integration, and tool registry

**Structure**:
```
gravity_core/
├── agents/                     # Agent implementations
│   ├── planner.py              # PLANNER - Creates TaskPlan DAGs
│   ├── coder.py                # CODER_* - Generates ChangeSets
│   ├── qa.py                   # QA - Tests and fixes
│   └── docs.py                 # DOCS - Documentation updates
├── tools/                      # 15+ registered tools
│   ├── runtime.py              # Sandbox execution
│   ├── git.py                  # Version control operations
│   └── files.py                # File manipulation
├── memory/                     # Context management
│   └── project_map.py          # Repository awareness (RAG)
├── llm/
│   └── client.py               # LLMClient (OpenAI/Gemini)
├── guardrails/                 # Safety and validation
├── utils/
│   └── crypto.py               # Fernet encryption
├── base.py                     # BaseAgent abstract class
├── schema.py                   # Explainability Contract (Pydantic)
└── tracking.py                 # Execution telemetry
```

**Key Patterns**:
- All agents inherit from BaseAgent
- Structured outputs via Pydantic schemas (TaskPlan, ChangeSet, ExecutionRun, DocUpdateLog)
- Tool-forcing for deterministic behavior (e.g., edit_file_snippet)
- RAG context injection from ProjectMap

### 2. Backend (backend/)

**Purpose**: State management, API endpoints, async task orchestration, and database persistence

**Structure**:
```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Pydantic Settings
│   ├── api/                    # REST + SSE endpoints
│   │   ├── repos.py            # Repository CRUD
│   │   ├── tasks.py            # Task execution
│   │   └── stream.py           # SSE streaming
│   ├── db/                     # SQLAlchemy models
│   │   ├── models.py           # Task, Repository, AgentRun
│   │   └── session.py          # Async session factory
│   ├── schemas/                # API request/response models
│   ├── services/               # Business logic layer
│   └── workers/
│       └── agent_runner.py     # Dramatiq orchestration pipeline
├── alembic/                    # Database migrations
│   ├── versions/               # Migration scripts
│   └── env.py                  # Migration environment
└── scripts/
    ├── gravity_cli.py          # CLI (repo, task, db commands)
    └── sync_schema.py          # Pydantic → TypeScript sync
```

**Key Patterns**:
- Async SQLAlchemy with asyncpg driver
- Dramatiq for background job processing (Redis broker)
- SSE streaming for real-time progress updates
- Alembic for schema versioning
- Typer-based CLI with Rich formatting

### 3. Frontend (frontend/)

**Purpose**: Visual rendering with real-time synchronization and user interaction

**Structure**:
```
frontend/
├── src/
│   ├── pages/                  # Route components
│   │   ├── Dashboard.jsx       # Repository overview
│   │   ├── TaskDetail.jsx      # Task execution view
│   │   └── RepoDetail.jsx      # Repository management
│   ├── components/             # Reusable UI components
│   │   ├── AgentCard.jsx       # Agent status display
│   │   ├── FileTree.jsx        # Repository file browser
│   │   ├── ActivityStream.jsx  # Real-time event feed
│   │   └── ui/                 # Shadcn components
│   ├── api/                    # API client functions
│   ├── hooks/                  # Custom React hooks
│   ├── types/                  # TypeScript definitions (synced from Pydantic)
│   ├── utils/                  # Helper functions
│   ├── App.jsx                 # Root component
│   └── main.jsx                # Vite entry point
├── vite.config.js              # Build configuration
├── tailwind.config.js          # Styling configuration
└── package.json                # Dependencies
```

**Key Patterns**:
- React Router v6 for client-side routing
- TanStack Query v5 for server state management (polling + caching)
- SSE hooks for real-time updates
- Shadcn UI with Tailwind for consistent styling
- Framer Motion for state transition animations

### 4. Tests (tests/)

**Purpose**: Comprehensive test coverage across all layers

**Structure**:
```
tests/
├── unit/                       # Isolated component tests
│   ├── gravity_core/           # Agent and tool tests
│   └── backend/                # Service and worker tests
├── integration/                # Multi-component tests
│   ├── test_api.py             # API endpoint tests
│   ├── test_database.py        # Database operations
│   └── test_dag_executor.py    # Pipeline execution
├── e2e/                        # Full workflow tests
│   ├── test_mission_lifecycle.py  # Complete task execution
│   └── test_workflow.py        # Multi-agent collaboration
└── conftest.py                 # Pytest fixtures
```

**Coverage**: 96+ tests (51+ Python, 45 JavaScript) with 100% pass rate

## Architectural Patterns

### 1. Brain-Body-Face Separation
- **Brain**: Stateless intelligence (GravityCore)
- **Body**: Stateful orchestration (FastAPI + Dramatiq)
- **Face**: Reactive UI (Vite + React)

### 2. Agent Pipeline (DAG Execution)
```
PLANNER → CODER → QA → DOCS → COMPLETED
```
- Topological sorting ensures dependency resolution
- Each agent produces structured output for next stage
- QA agent can loop back to CODER for fixes (max 3 attempts)

### 3. Explainability Contract
Every agent decision is captured in Pydantic schemas:
- **TaskPlan**: Steps, dependencies, assigned agents
- **ChangeSet**: File diffs with line-level precision
- **ExecutionRun**: Test results, stdout/stderr, exit codes
- **DocUpdateLog**: Documentation changes with rationale

### 4. Sandbox Isolation
- Docker containers with no network access
- 512MB RAM limit, read-only filesystem
- Temporary workspace mounted at /sandbox/project
- Command blocking for dangerous patterns (rm -rf, curl, wget)

### 5. Real-Time Synchronization
- **SSE Streaming**: Server pushes progress updates
- **TanStack Query Polling**: Client polls for state changes (5s interval)
- **Optimistic Updates**: UI reflects changes before server confirmation

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  (Vite + React 18 + TanStack Query + SSE)                   │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API + SSE
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  (SQLAlchemy + Dramatiq + Redis + PostgreSQL)               │
└────────────────────┬────────────────────────────────────────┘
                     │ Agent Invocation
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                       GravityCore                            │
│  (BaseAgent + LLMClient + Tools + ProjectMap)               │
└────────────────────┬────────────────────────────────────────┘
                     │ LLM API Calls
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   OpenAI / Gemini                            │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Files

- **pyproject.toml**: Python dependencies, build config, tool settings (ruff, pytest, mypy)
- **alembic.ini**: Database migration configuration
- **docker-compose.yml**: PostgreSQL, Redis, and sandbox container definitions
- **Dockerfile.sandbox**: Isolated execution environment
- **.env**: Environment variables (API keys, database URLs)
- **vite.config.js**: Frontend build configuration
- **tailwind.config.js**: UI styling system
