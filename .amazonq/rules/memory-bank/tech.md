# Technology Stack

## Programming Languages

### Python 3.11+
- **Primary Backend Language**: All agent logic, API, and orchestration
- **Type Hints**: Strict mypy configuration for type safety
- **Async/Await**: Native asyncio for concurrent operations

### JavaScript (ES2022+)
- **Frontend Language**: React 18 with modern JSX syntax
- **Module System**: ES modules with Vite bundler
- **Type Safety**: JSDoc annotations with TypeScript checking

## Core Technologies

### Backend Stack

#### Web Framework
- **FastAPI 0.115.0+**: Modern async web framework
  - Automatic OpenAPI documentation
  - Pydantic integration for validation
  - SSE support via sse-starlette

#### Database
- **PostgreSQL 16**: Primary data store
- **SQLAlchemy 2.0+**: Async ORM with asyncpg driver
- **Alembic 1.14.0+**: Database migration management
- **Redis 7**: Task queue broker and caching

#### Task Queue
- **Dramatiq 1.17.0+**: Distributed task processing
  - Redis broker for message passing
  - Worker processes for background jobs
  - Retry logic with exponential backoff

#### LLM Integration
- **OpenAI SDK 1.57.0+**: GPT-4o and GPT-4o-mini
- **Google Generative AI 0.8.0+**: Gemini models
- **Custom LLMClient**: Unified interface with fallback logic

#### Security & Utilities
- **Cryptography 42.0.0+**: Fernet encryption for secrets
- **Docker SDK 7.1.0+**: Sandbox container management
- **Tenacity 8.2.0+**: Retry decorators with backoff
- **Structlog 24.4.0+**: Structured logging

### Frontend Stack

#### Build System
- **Vite 6.1.0**: Lightning-fast HMR and optimized builds
- **@vitejs/plugin-react 4.3.4+**: React Fast Refresh support

#### UI Framework
- **React 18.2.0**: Component-based UI library
- **React Router 6.26.0+**: Client-side routing
- **React Hook Form 7.54.2+**: Form state management

#### State Management
- **TanStack Query 5.84.1+**: Server state synchronization
  - Automatic caching and invalidation
  - Polling with configurable intervals
  - Optimistic updates

#### UI Components
- **Shadcn UI**: Accessible component library built on Radix UI
- **Radix UI Primitives**: Unstyled, accessible components
- **Lucide React 0.475.0+**: Icon library
- **Framer Motion 11.16.4+**: Animation library

#### Styling
- **Tailwind CSS 3.4.17+**: Utility-first CSS framework
- **tailwindcss-animate**: Animation utilities
- **class-variance-authority**: Component variant management
- **clsx + tailwind-merge**: Conditional class merging

#### Additional Libraries
- **React Markdown 9.0.1+**: Markdown rendering
- **date-fns 3.6.0+**: Date manipulation
- **Zod 3.24.2+**: Schema validation
- **Sonner 2.0.1+**: Toast notifications

### Development Tools

#### Python Tooling
- **uv**: Fast Python package installer and resolver
- **Ruff 0.8.0+**: Linter and formatter (replaces Black, isort, flake8)
- **Mypy 1.13.0+**: Static type checker
- **Pytest 8.3.0+**: Testing framework
  - pytest-asyncio: Async test support
  - pytest-cov: Coverage reporting
  - pytest-mock: Mocking utilities

#### JavaScript Tooling
- **ESLint 9.19.0+**: Linter with React plugins
- **Prettier** (via ESLint): Code formatting
- **TypeScript 5.8.2+**: Type checking (via JSDoc)

#### CLI Tools
- **Typer 0.14.0+**: CLI framework with Rich integration
- **Rich 13.9.0+**: Terminal formatting and progress bars
- **Honcho 2.0.0+**: Process manager (Procfile support)

## Infrastructure

### Containerization
- **Docker**: Sandbox isolation and development environment
- **Docker Compose**: Multi-container orchestration
  - PostgreSQL service
  - Redis service
  - Sandbox container (python:3.11-slim)

### Sandbox Configuration
```dockerfile
FROM python:3.11-slim
# No network access, 512MB RAM limit
# Includes: pytest, black, ruff, mypy
# Non-root user: sandbox
```

## Development Commands

### Python Backend

#### Installation
```bash
# Install with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

#### Running Services
```bash
# Start infrastructure
docker-compose up -d postgres redis

# Run API server
uvicorn backend.app.main:app --reload --port 8000

# Run worker processes
dramatiq backend.app.workers --processes 2 --threads 4

# Run all services (Procfile)
honcho start
```

#### Database Management
```bash
# Apply migrations
gravity db upgrade head

# Revert migration
gravity db downgrade -1

# Create new migration
gravity db revision -m "description"

# Show current version
gravity db current

# Show migration history
gravity db history
```

#### CLI Operations
```bash
# Repository management
gravity repo add /path/to/repo --name "Project"
gravity repo list
gravity repo scan <repo-id>

# Task execution
gravity task run <repo-id> "Feature description"
gravity task status <task-id>
gravity task list --repo-id <repo-id>
```

#### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=libs --cov=backend --cov-report=html

# Run specific test file
pytest tests/unit/gravity_core/test_agents.py

# Run with verbose output
pytest -v -s
```

#### Linting & Formatting
```bash
# Check code
ruff check .

# Format code
ruff format .

# Type checking
mypy libs backend
```

### Frontend

#### Installation
```bash
cd frontend
npm install
```

#### Development
```bash
# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

#### Code Quality
```bash
# Lint
npm run lint

# Lint with auto-fix
npm run lint:fix

# Type checking
npm run typecheck
```

### Schema Synchronization

```bash
# Sync Pydantic models to TypeScript
sync-schema

# Manual sync
python backend/scripts/sync_schema.py
```

## Environment Variables

### Required
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/antigravity

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM Providers (at least one required)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Encryption
ANTIGRAVITY_ENCRYPTION_KEY=<fernet-key>
```

### Optional
```bash
# LLM Configuration
DEFAULT_LLM_PROVIDER=openai  # or gemini
DEFAULT_LLM_MODEL=gpt-4o
ENABLE_LLM_FALLBACK=true

# Agent Configuration
CONFIDENCE_REVIEW_THRESHOLD=0.7
MAX_QA_RETRIES=3

# Sandbox Configuration
SANDBOX_TIMEOUT=300
SANDBOX_MEMORY_LIMIT=512m
```

## Build System

### Python (Hatchling)
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["libs", "backend"]
```

### JavaScript (Vite)
```javascript
// vite.config.js
export default {
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: 'dist' }
}
```

## Version Control

### Git Workflow
- **Main Branch**: Production-ready code
- **Feature Branches**: Individual features/fixes
- **CI/CD**: GitHub Actions for testing and deployment

### Pre-commit Hooks
```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Testing Infrastructure

### Python Tests
- **Unit Tests**: 30+ tests for agents, tools, utilities
- **Integration Tests**: 15+ tests for API, database, DAG execution
- **E2E Tests**: 6+ tests for full mission lifecycle

### JavaScript Tests
- **Component Tests**: 45 tests with Jest + React Testing Library
- **Coverage**: Comprehensive UI component testing

## Performance Considerations

- **Async Operations**: All I/O operations use asyncio
- **Connection Pooling**: SQLAlchemy async engine with pool size 10
- **Query Optimization**: TanStack Query caching reduces API calls
- **SSE Streaming**: Real-time updates without polling overhead
- **Worker Scaling**: Dramatiq supports horizontal scaling
