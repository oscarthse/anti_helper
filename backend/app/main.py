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

from backend.app.api import repos, streaming, tasks
from backend.app.db.session import init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("application_starting")

    # Initialize database
    await init_db()

    yield

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

# Include routers
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(repos.router, prefix="/api/repos", tags=["repos"])
app.include_router(streaming.router, prefix="/api/stream", tags=["streaming"])


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
