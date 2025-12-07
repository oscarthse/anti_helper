# 🧠 Antigravity Dev: Project Memory and Context

## 1. Project Overview & Status

**Goal:** A multi-agent, sandboxed AI development platform that plans, edits, and tests changes across complex applications as a disciplined engineering team.

**Current Phase:** Phase 5: Infrastructure & Frontend

**Last Updated:** 2025-12-07T19:07:00+01:00

**Architecture:** Brain-Body-Face

| Component | Role | Status |
| :--- | :--- | :--- |
| **THE BRAIN** (GravityCore) | Agent personas, LLM client, tools, context | ✅ Complete |
| **THE BODY** (FastAPI) | State manager, API gateway, worker orchestration, migrations | ✅ Complete |
| **THE FACE** (Next.js) | Visual renderer, streaming UI | ⏳ Components done, pages pending |

---

## 2. Core Architectural Principles

| Principle | Detail |
| :--- | :--- |
| **Explainability First** | All agent output conforms to `AgentOutput` schema with `ui_title`, `ui_subtitle`, `confidence_score` |
| **Single Source of Truth** | All state in PostgreSQL via SQLAlchemy Async; migrations managed by Alembic |
| **Safety & Isolation** | All shell commands via Docker Sandbox (no network, 512MB RAM, read-only) |
| **Type Integrity** | Pydantic types auto-synced to TypeScript |
| **Structured Output** | LLM responses forced to Pydantic schemas via tool-calling |
| **Secret Security** | API keys encrypted at rest using Fernet |

---

## 3. Technology Stack

| Component | Technology | Location |
| :--- | :--- | :--- |
| **Package Manager** | uv | `pyproject.toml` |
| **Database** | PostgreSQL 16 + asyncpg | `backend/app/db/` |
| **Migrations** | Alembic | `backend/alembic/` |
| **LLM Providers** | OpenAI + Gemini | `libs/gravity_core/llm/` |
| **Encryption** | Fernet | `libs/gravity_core/utils/crypto.py` |
| **Task Queue** | Dramatiq + Redis | `backend/app/workers/` |
| **Frontend** | Next.js + TypeScript | `frontend/` |
| **Testing** | Pytest + Jest | `tests/` + `frontend/tests/` |

---

## 4. Implementation Status

### 4.1 ✅ Completed Components

**All Agents (Brain)**
- [x] **PlannerAgent** - RAG context, TaskPlan generation (15 tests)
- [x] **CoderAgent** - Tool-forcing, ChangeSet output, BE/FE/Infra variants
- [x] **QAAgent** - Test execution, LLM diagnosis, fix generation (Code→Test→Fix loop)
- [x] **DocsAgent** - CHANGELOG, README, docstring updates via tool-calling (10 tests)

**Worker Orchestration (Body)**
- [x] Full pipeline: `_run_planning_phase` → `_run_execution_phase` → `_run_documentation_phase`
- [x] Code→Test→Fix loop with max 3 fix attempts
- [x] Confidence-based state transitions
- [x] `resume_task()` for post-review continuation (7 tests)

**Database & Migrations**
- [x] Alembic setup with async model support
- [x] Initial migration: repositories, repository_secrets, tasks, agent_logs, changesets
- [x] CLI integration (`gravity db upgrade/downgrade/revision`)

**Security**
- [x] Fernet encryption for secrets (9 tests)
- [x] `RepositorySecret` model
- [x] Environment-based key management

**Frontend Components**
- [x] AgentCard, LiveStream, TaskPlan (45 tests, 100% passing)

### 4.2 📋 Pending Tasks

**Frontend Pages**
- [ ] Dashboard page
- [ ] Repository management page
- [ ] Task detail page with diff viewer
- [ ] Settings page

**Infrastructure**
- [ ] GitHub Actions CI/CD
- [ ] Production deployment guide

---

## 5. Test Suite Status

| Suite | Count | Status |
|-------|-------|--------|
| `test_planner.py` | 15 | ✅ |
| `test_docs.py` | 10 | ✅ |
| `test_crypto.py` | 9 | ✅ |
| `test_worker.py` | 7 | ✅ |
| `test_llm_client.py` | 12 | ✅ |
| Frontend (Jest) | 45 | ✅ |
| **Total** | **96+** | ✅ 100% pass rate |

---

## 6. Architectural Decisions Log (ADR)

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Next.js + TypeScript | SSR, type safety, ecosystem |
| ADR-002 | Dramatiq + Docker Sandbox | Decoupled execution, security |
| ADR-003 | Mandatory AgentOutput | Explainability, auditability |
| ADR-004 | Sandbox Security | No network, memory limits, read-only |
| ADR-005 | PostgreSQL as SSOT | Resilience, observability |
| ADR-006 | Decorator-based tools | Easy registration, JSON Schema |
| ADR-007 | LLM Multi-Provider | Reduced lock-in, fallback |
| ADR-008 | Fernet Encryption | Secrets protected at rest |
| ADR-009 | Alembic with importlib | Bypasses async engine during migrations |

---

## 7. File Structure Reference

```
anti_helper/
├── pyproject.toml
├── alembic.ini                 # Alembic config ✅
├── docker-compose.yml
├── Dockerfile / Dockerfile.sandbox
│
├── libs/gravity_core/          # THE BRAIN ✅
│   ├── schema.py
│   ├── base.py
│   ├── agents/
│   │   ├── planner.py          # ✅ LLM integrated
│   │   ├── coder.py            # ✅ LLM integrated
│   │   ├── qa.py               # ✅ LLM integrated (diagnosis + fix)
│   │   └── docs.py             # ✅ LLM integrated (tool-calling)
│   ├── tools/
│   ├── memory/
│   ├── llm/
│   │   └── client.py           # ✅ Multi-provider
│   └── utils/
│       └── crypto.py           # ✅ Fernet encryption
│
├── backend/                    # THE BODY ✅
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── streaming.py    # ✅ SSE
│   │   ├── db/
│   │   │   └── models.py       # ✅ All models
│   │   └── workers/
│   │       └── agent_runner.py # ✅ Full pipeline
│   ├── alembic/                # ✅ NEW
│   │   ├── env.py              # importlib model loading
│   │   └── versions/           # Migration scripts
│   └── scripts/
│       └── gravity_cli.py      # ✅ db commands added
│
├── frontend/                   # THE FACE (partial)
│   ├── src/components/         # ✅ Complete
│   └── tests/                  # ✅ 45 tests
│
└── tests/
    ├── unit/gravity_core/
    │   ├── test_planner.py     # 15 ✅
    │   ├── test_docs.py        # 10 ✅
    │   ├── test_crypto.py      # 9 ✅
    │   └── test_llm_client.py  # 12 ✅
    └── unit/backend/
        └── test_worker.py      # 7 ✅
```

---

## 8. Quick Reference Commands

```bash
# Development Setup
cp .env.example .env
docker-compose up -d postgres redis
uv pip install -e ".[dev]"

# Database Migrations
alembic upgrade head                           # Apply all
alembic downgrade -1                           # Revert one
alembic revision --autogenerate -m "message"   # New migration

# CLI Shortcuts
gravity db upgrade head
gravity db revision -m "new feature"

# Run Services
uvicorn backend.app.main:app --reload
dramatiq backend.app.workers --processes 2

# Testing (100% pass rate)
pytest tests/unit/                             # Python
cd frontend && npm test                        # Frontend
```

---

## 9. Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL async connection | Yes |
| `REDIS_URL` | Redis connection | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes (or GOOGLE_API_KEY) |
| `GOOGLE_API_KEY` | Google AI API key | No (fallback) |
| `DEFAULT_LLM_PROVIDER` | `openai` or `gemini` | No |
| `DEFAULT_LLM_MODEL` | Model name | No (default: gpt-4o) |
| `CONFIDENCE_REVIEW_THRESHOLD` | Human review threshold | No (0.7) |
| `ANTIGRAVITY_ENCRYPTION_KEY` | Fernet key | Yes (for secrets) |

---

## 10. Session Changelog

### 2025-12-07

**Completed:**
- ✅ QAAgent with LLM diagnosis and Code→Test→Fix loop
- ✅ DocsAgent with tool-calling for CHANGELOG/README/docstrings
- ✅ Worker pipeline: Plan → Code → Test → Fix → Docs → COMPLETED
- ✅ Alembic migrations setup (importlib approach)
- ✅ CLI `db` command group (upgrade, downgrade, revision, current, history)
- ✅ Initial migration generated and applied (5 tables)
- ✅ All tests passing (96+ total, 100% pass rate)

**Files Created/Modified:**
- `libs/gravity_core/agents/qa.py` - Full LLM implementation
- `libs/gravity_core/agents/docs.py` - Full LLM implementation
- `backend/app/workers/agent_runner.py` - Full pipeline
- `backend/alembic/env.py` - importlib model loading
- `backend/alembic/versions/5803305ba5cd_initial_database_schema.py`
- `backend/scripts/gravity_cli.py` - db commands
- `tests/unit/gravity_core/test_docs.py` - 10 tests
- `frontend/tests/components/LiveStream.test.tsx` - Fixed multiple elements bug
