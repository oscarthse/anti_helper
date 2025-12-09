# Product Overview

## Project Purpose

Antigravity Dev is a repo-aware, sandboxed, multi-agent AI development platform that functions as a disciplined engineering team. It autonomously plans, edits, and tests changes across complex applications by orchestrating specialized AI agents that collaborate through a structured pipeline.

## Value Proposition

- **Autonomous Development**: Transforms natural language requirements into production-ready code through a multi-agent pipeline
- **Repository Intelligence**: Maintains deep contextual awareness of codebases through ProjectMap memory system
- **Sandboxed Execution**: Guarantees safe code execution in isolated Docker containers with resource limits
- **Explainable AI**: Every agent decision is tracked with structured outputs (TaskPlan, ChangeSet, ExecutionRun, DocUpdateLog)
- **Quality Assurance**: Built-in QA agent automatically tests changes and iterates on fixes (max 3 attempts)
- **Real-Time Visibility**: Live progress tracking through SSE streaming and TanStack Query polling

## Key Features

### Multi-Agent Pipeline
- **PLANNER**: Analyzes requirements and creates DAG-based execution plans with topological sorting
- **CODER** (BE/FE/INFRA): Generates precise code diffs using tool-forcing (edit_file_snippet)
- **QA**: Runs tests in sandbox, diagnoses failures, and suggests fixes
- **DOCS**: Updates CHANGELOG, README, and docstrings with structured tool-calling

### Core Capabilities
- **15+ Registered Tools**: Runtime execution, Git operations, file manipulation, and more
- **LLM Integration**: OpenAI and Gemini support with automatic fallback and retry logic
- **Secret Encryption**: Fernet-based encryption for API keys at rest
- **Database Migrations**: Alembic-powered schema versioning with CLI commands
- **Command Blocking**: Automatic detection and prevention of dangerous shell patterns

### Frontend Experience
- **Vite + React 18**: Modern build system with fast HMR
- **TanStack Query v5**: Optimistic updates and intelligent caching
- **Shadcn UI**: Accessible component library with Tailwind styling
- **Framer Motion**: Smooth animations for agent state transitions
- **Real-Time Updates**: SSE streaming for live progress and activity feeds

## Target Users

### Primary Users
- **Solo Developers**: Need an AI pair programmer that handles full feature implementation
- **Small Teams**: Want to accelerate development velocity without hiring additional engineers
- **Technical Leads**: Require explainable AI decisions for code review and approval workflows

### Use Cases
1. **Feature Development**: "Add input validation to user registration endpoint" → Full implementation with tests
2. **Bug Fixes**: "Fix memory leak in background worker" → Diagnosis, fix, and verification
3. **Refactoring**: "Extract authentication logic into reusable service" → Safe structural changes
4. **Documentation**: "Update API docs for new endpoints" → Automated doc generation
5. **Infrastructure**: "Add Redis caching layer" → Config changes, code updates, and deployment scripts

## Architecture Philosophy

**Brain-Body-Face** separation ensures clean boundaries:
- **Brain (GravityCore)**: Pure intelligence layer with agent personas and LLM integration
- **Body (FastAPI)**: State management, task orchestration, and async job processing
- **Face (Frontend)**: Visual rendering with real-time synchronization

## Quality Standards

- **Protocol "Verified Reality"**: Sledgehammer verification ensures files are physically written to disk
- **Minimum Code Volume**: Coder agents enforce substantial implementations (no placeholders)
- **README Mandate**: Agent prompts require project-specific documentation (no generic templates)
- **Test Coverage**: 96+ tests across Python and JavaScript with 100% pass rate
