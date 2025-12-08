# 🚀 Antigravity Dev

> A repo-aware, sandboxed, multi-agent AI development platform that plans, edits, and tests changes across complex applications as a disciplined engineering team.
>
> **[📘 Read the Technical Deep Dive (Neuro-Symbolic Architecture)](md/TECHNICAL.md)**

## 🏗️ Architecture

**Brain-Body-Face** architecture:

| Component | Role | Technology |
|-----------|------|------------|
| **THE BRAIN** (GravityCore) | Intelligence & Skillset | Custom Python library with agent personas, LLM integration (`client.py`), and 15+ tools |
| **THE BODY** (FastAPI) | State Manager & Dispatcher | FastAPI, SQLAlchemy Async, Dramatiq, Redis, Alembic |
| **THE FACE** (Frontend) | Visual Renderer | Next.js 14, TypeScript, Tailwind, Shadcn UI, Framer Motion |

**Recent Critical Updates (Dec 2025):**
- 🛡️ **Protocol "Verified Reality":** "Sledgehammer" verification logic guarantees files are physically written to disk.
- 🧠 **Technical Mandate:** Planner now enforces strict implementation specs, eliminating "lazy placeholder" code.
- 🕹️ **Headless Debugger:** `scripts/run_agent.py` allows rapid Agent verification without the full backend stack.

## 🤖 Agent Personas

| Agent | Role | Key Output | Status |
|-------|------|------------|--------|
| `PLANNER` | Product Manager | TaskPlan (steps to execute) | ✅ Complete |
| `CODER_BE/FE/INFRA` | Engineers | ChangeSet (code diffs) | ✅ Complete |
| `QA` | Automated Debugger | ExecutionRun + Fix suggestions | ✅ Complete |
| `DOCS` | Technical Scribe | DocUpdateLog (doc updates) | ✅ Complete |

**Full Pipeline:** `Plan → Code → Test → Fix → Docs → COMPLETED`

## 📦 Project Structure

```
antigravity-dev/
├── libs/gravity_core/          # The Brain
│   ├── schema.py               # Explainability Contract (Pydantic)
│   ├── base.py                 # BaseAgent class
│   ├── agents/                 # All LLM-integrated agents
│   │   ├── planner.py          # PLANNER ✅
│   │   ├── coder.py            # CODER_* ✅
│   │   ├── qa.py               # QA (diagnose + fix) ✅
│   │   └── docs.py             # DOCS ✅
│   ├── tools/                  # 15 registered tools (Runtime, Git, Files)
│   ├── memory/                 # ProjectMap context manager
│   ├── llm/
│   │   └── client.py           # LLMClient (OpenAI/Gemini)
│   └── utils/
│       └── crypto.py           # Secret encryption (Fernet)
│
├── backend/                    # The Body
│   ├── app/
│   │   ├── main.py             # FastAPI entry
│   │   ├── config.py           # Pydantic Settings
│   │   ├── api/                # REST + SSE endpoints
│   │   ├── db/                 # SQLAlchemy models
│   │   └── workers/
│   │       └── agent_runner.py # Full orchestration pipeline
│   ├── alembic/                # Database migrations
│   │   ├── env.py              # Migration environment
│   │   └── versions/           # Migration scripts
│   └── scripts/
│       └── gravity_cli.py      # CLI (repo, task, db commands)
│
├── frontend/                   # The Face (Next.js 14)
│   ├── src/
│   │   ├── app/                # App Router Layouts & Pages
│   │   ├── components/         # Shadcn UI + AgentCard
│   │   └── types/              # Synced with Python Pydantic models
│   ├── tests/                  # Jest + RTL tests (45 passing)
│   └── tailwind.config.ts      # Zinc Theme Configuration
│
├── tests/                      # Python test suite (51+ passing)
│   ├── unit/gravity_core/      # Agent + utility tests
│   └── unit/backend/           # Worker tests
│
├── alembic.ini                 # Alembic configuration
├── docker-compose.yml          # Infrastructure
└── Dockerfile.sandbox          # Isolated execution env
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Frontend)
- Docker & Docker Compose
- PostgreSQL 16, Redis 7

### Installation

```bash
# 1. Install Python dependencies
uv pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY and ANTIGRAVITY_ENCRYPTION_KEY

# 3. Start infrastructure (DB + Redis)
docker-compose up -d postgres redis

# 4. Run database migrations
gravity db upgrade head

# 5. Start the API
uvicorn backend.app.main:app --reload

# 6. Start the Worker (in a separate terminal)
dramatiq backend.app.workers --processes 2

# 7. Start the Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
# Visit http://localhost:3000
```

### CLI Commands

```bash
# Repository management
gravity repo add /path/to/repo --name "My Project"
gravity repo scan <repo-id>

# Task execution
gravity task run <repo-id> "Add input validation to the user registration endpoint"
gravity task status <task-id>

# Database migrations
gravity db upgrade head      # Apply all migrations
gravity db downgrade -1      # Revert one migration
gravity db revision -m "new" # Create new migration
gravity db current           # Show current revision
gravity db history           # Show migration history
```

## 🔄 Agent Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     FULL AGENT PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. PLANNER    TaskPlan (DAG) with steps, assigned agents                │
│       │        (RAG context from ProjectMap + Topological Sort)          │
│       ▼                                                                  │
│  2. CODER      ChangeSet with diffs per step                             │
│       │        (tool-forcing: edit_file_snippet)                         │
│       ▼                                                                  │
│  3. QA         Run tests, diagnose failures                              │
│       │        (Code → Test → Fix loop, max 3 attempts)                  │
│       ▼                                                                  │
│  4. DOCS       Update CHANGELOG, README, docstrings                      │
│       │        (tool-calling for structured updates)                     │
│       ▼                                                                  │
│  ✅ COMPLETED                                                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🔑 LLM Integration

```python
from gravity_core.llm import LLMClient

client = LLMClient(
    openai_api_key="...",
    gemini_api_key="...",
    enable_fallback=True,
    max_retries=3,
)

# Structured output
result = await client.generate_structured_output(
    prompt="Create a plan for...",
    output_schema=TaskPlan,
)

# Tool-calling
response = await client.generate_with_tools(
    prompt="Edit the file...",
    tools=[...],
    tool_choice="required",
)
```

## 🔒 Security

- **Sandbox Isolation**: Docker containers with no network, 512MB RAM, read-only filesystem
- **Secret Encryption**: Fernet encryption for API keys at rest
- **Command Blocking**: Dangerous patterns blocked automatically

## 🛠️ Development

```bash
# Run all tests
pytest
cd frontend && npm test

# Lint & format
ruff check . && ruff format .
```

## 📊 Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| Python (total) | 51+ | ✅ All passing |
| Frontend | 45 | ✅ All passing |
| **Combined** | **96+** | ✅ 100% pass rate |

## 📝 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google AI API key | - |
| `DEFAULT_LLM_PROVIDER` | `openai` or `gemini` | `openai` |
| `DEFAULT_LLM_MODEL` | Model name | `gpt-4o` |
| `CONFIDENCE_REVIEW_THRESHOLD` | Human review threshold | `0.7` |
| `ANTIGRAVITY_ENCRYPTION_KEY` | Fernet encryption key | - |

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
