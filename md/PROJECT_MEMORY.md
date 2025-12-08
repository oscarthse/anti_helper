# 🧠 Antigravity Dev: Project Memory and Context

## 1. Project Overview & Status

**Goal:** A multi-agent, sandboxed AI development platform that plans, edits, and tests changes across complex applications as a disciplined engineering team.

**Current Phase:** Phase 5: Infrastructure & Frontend (The Face)

**Last Updated:** 2025-12-07T21:20:00+01:00

**Architecture:** Brain-Body-Face

| Component | Role | Status |
| :--- | :--- | :--- |
| **THE BRAIN** (GravityCore) | Agent personas, LLM client, tools, context | ✅ Complete |
| **THE BODY** (FastAPI) | State manager, API gateway, worker orchestration, migrations | ✅ Complete |
| **THE FACE** (Next.js) | Visual renderer, streaming UI, Shadcn foundation | 🚧 In Progress (Foundation Built) |

---

## 2. Core Architectural Principles

| Principle | Detail |
| :--- | :--- |
| **Explainability First** | All agent output conforms to `AgentOutput` schema with `ui_title`, `ui_subtitle`, `confidence_score` |
| **Single Source of Truth** | All state in PostgreSQL via SQLAlchemy Async; migrations managed by Alembic |
| **Safety & Isolation** | All shell commands via Docker Sandbox (no network, 512MB RAM, read-only) |
| **Type Integrity** | Pydantic types auto-synced to TypeScript (`frontend/types/schema.ts`) |
| **Structured Output** | LLM responses forced to Pydantic schemas via tool-calling |
| **Secret Security** | API keys encrypted at rest using Fernet |
| **Premium Aesthetic** | "Generative UI" vibe using Shadcn, Framer Motion, and Zinc Dark theme |

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
| **Frontend** | Next.js 14 + TS + Tailwind + Shadcn | `frontend/` |
| **UI Library** | Radix Primitives + Framer Motion | `frontend/src/components/` |
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
- [x] **[P1] Sandbox Hardening:** Disabled silent local fallback (Gatekeeper Audit)

**Frontend Components**
- [x] **Foundation:** Next.js 14, Tailwind, Shadcn UI setup
- [x] **Core Primitives:** Card, Badge, Button, Accordion, Utility (`cn`)
- [x] **Smart Components:**
  - `AgentCard` (Animated, status-aware, collapsible details)
  - `LiveStream` (SSE integration)
  - `TaskPlan` (Visual progress tracking)
- [x] **Type Sync:** Automated Pydantic → TypeScript schema generation
- [x] **Testing:** Jest unit tests for components (45 tests passing)
- [x] **CI/CD:** GitHub Actions pipeline configured and passing (Unit + Integration)

### 4.2 📋 Pending Tasks

**Frontend Pages**
- [ ] Dashboard Page (`/dashboard`) - Task grid & stats
- [ ] Task "War Room" (`/task/[id]`) - Split view (Stream + Context)
- [ ] Repository Management Modal

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
| ADR-010 | Shadcn + Framer Motion | Premium "Generative UI" aesthetic |

---

## 7. File Structure Reference

```
anti_helper/
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── Dockerfile / Dockerfile.sandbox
│
├── libs/gravity_core/          # THE BRAIN ✅
│   ├── schema.py               # Pydantic models
│   ├── agents/                 # Planner, Coder, QA, Docs
│   ├── tools/                  # Runtime (Fixed P1/P2), Web, File ops
│   └── llm/                    # Client
│
├── backend/                    # THE BODY ✅
│   ├── app/
│   │   ├── api/
│   │   │   ├── tasks.py        # ✅ Fixed P0 (Worker dispatch)
│   │   │   └── streaming.py    # SSE
│   │   ├── db/models.py
│   │   └── workers/
│   │       └── agent_runner.py # Pipeline
│   └── alembic/                # Migrations
│
├── frontend/                   # THE FACE (In Progress)
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   │   ├── layout.tsx      # Root layout
│   │   │   ├── globals.css     # Zinc Dark Theme
│   │   │   └── page.tsx        # Landing
│   │   ├── components/
│   │   │   ├── ui/             # Shadcn primitives (Card, Badge...)
│   │   │   ├── AgentCard.tsx   # ✅ High-fidelity
│   │   │   └── LiveStream.tsx  # ✅ SSE wired
│   │   ├── lib/
│   │   │   └── utils.ts        # cn() helper
│   │   └── types/
│   │       └── schema.ts       # ✅ Synced interfaces
│
└── tests/                      # Python test suite
```

---

## 8. Quick Reference Commands

```bash
# Development Setup
cp .env.example .env
docker-compose up -d postgres redis
uv pip install -e ".[dev]"

# Frontend Development
cd frontend
npm install
npm run dev

# Database Migrations
gravity db upgrade head

# Run Services (Backend)
uvicorn backend.app.main:app --reload
dramatiq backend.app.workers --processes 2
```

---

## 9. Session Changelog

### 2025-12-07

**Critical Audit Repairs (Gatekeeper Findings):**
- 🛑 **[P0] Task Dispatch Fixed:** Connectivity restored in `tasks.py`.
- 🛡️ **[P1] Security Hole Closed:** Removed silent local fallback in `runtime.py`.
- ⚡ **[P2] Async Safety:** Wrapped blocking DB calls in `asyncio.to_thread`.

**Frontend Foundation:**
- ✅ **Tech Stack:** Next.js 14, TypeScript, Tailwind, Shadcn UI.
- ✅ **Architecture:** `schema.ts` synced with Pydantic models.
- ✅ **UI Components:** Implemented `AgentCard` (Animated), `Badge`, `Card`, `Accordion`.
- ✅ **Theme:** Configured Zinc Dark Mode in `globals.css` / `tailwind.config.ts`.

**Completed:**
- ✅ QAAgent with LLM diagnosis and Code→Test→Fix loop
- ✅ DocsAgent with tool-calling for CHANGELOG/README/docstrings
- ✅ Worker pipeline: Plan → Code → Test → Fix → Docs → COMPLETED
- ✅ Alembic migrations setup & initial migration
- ✅ All tests passing (96+ total)

**Infrastructure:**
- ✅ **CI/CD:** `ci.yml` pipeline operational (Fixed `psycopg2` dependency, venv installation)
- ✅ **Makefile:** Standardized development commands (`make dev`, `make test-all`)
