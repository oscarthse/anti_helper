"""
Antigravity Dev - FastAPI Application

The main API entry point. Handles all I/O, manages the Database,
and dispatches heavy tasks to the workers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import repos, streaming, tasks, dashboard, files
from backend.app.db.session import init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("application_starting")

    # Initialize database
    await init_db()

    # Initialize Redis EventBus for real-time SSE streaming
    # This replaces database polling with efficient pub/sub
    from backend.app.core.events import init_event_bus, shutdown_event_bus
    try:
        await init_event_bus()
        logger.info("redis_event_bus_initialized")
    except Exception as e:
        logger.warning("redis_event_bus_init_failed", error=str(e))
        # Continue without Redis - SSE will still work via initial fetch

    yield

    # Cleanup
    try:
        await shutdown_event_bus()
    except Exception:
        pass

    logger.info("application_shutting_down")


app = FastAPI(
    title="Antigravity Dev API",
    description="A repo-aware, sandboxed, multi-agent AI development platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - allow multiple localhost ports (Next.js can use different ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5200",  # Next.js alternative port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(repos.router, prefix="/api/repos", tags=["repos"])
app.include_router(streaming.router, prefix="/api/stream", tags=["streaming"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(files.router, prefix="/api/files", tags=["files"])


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "name": "Antigravity Dev API",
        "version": "0.1.0",
        "status": "healthy",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
