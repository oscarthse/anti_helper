"""
Shared Pytest Fixtures

This module contains fixtures used across all test layers:
- Database session fixtures
- Mock LLM client fixtures
- Factory fixtures for test data
"""

import asyncio

# Add project root to path
# Add project root to path
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# =============================================================================
# Event Loop Fixture
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================


# Use SQLite for testing (in-memory for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Import models to ensure they're registered
    from backend.app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Test Data Factories
# =============================================================================


@pytest.fixture
def sample_repository_data() -> dict:
    """Sample repository data for testing."""
    return {
        "id": uuid4(),
        "name": "test-repo",
        "path": "/tmp/test-repo",
        "description": "A test repository",
        "project_type": "python",
        "framework": "fastapi",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@pytest.fixture
def sample_task_data(sample_repository_data) -> dict:
    """Sample task data for testing."""
    return {
        "id": uuid4(),
        "repo_id": sample_repository_data["id"],
        "user_request": "Add input validation to the user registration endpoint",
        "title": "Add Validation",
        "status": "pending",
        "current_agent": None,
        "current_step": 0,
        "task_plan": None,
        "error_message": None,
        "retry_count": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "completed_at": None,
    }


@pytest.fixture
def sample_agent_output_data() -> dict:
    """Sample AgentOutput data for testing."""
    return {
        "ui_title": "Analyzing Repository Structure",
        "ui_subtitle": "I'm scanning your codebase to understand the project layout.",
        "technical_reasoning": "Scanning repo structure to identify key files and patterns.",
        "tool_calls": [
            {
                "tool_name": "scan_repo_structure",
                "arguments": {"path": "/tmp/test-repo"},
                "result": '{"files": 10, "directories": 3}',
                "success": True,
            }
        ],
        "confidence_score": 0.85,
        "agent_persona": "planner",
    }


@pytest.fixture
def sample_task_plan_data() -> dict:
    """Sample TaskPlan data for testing."""
    return {
        "summary": "Add input validation to user registration",
        "steps": [
            {
                "step_id": "step-1",
                "order": 1,
                "description": "Analyze existing endpoint",
                "agent_persona": "planner",
                "depends_on": [],
                "files_affected": ["backend/app/api/users.py"],
            },
            {
                "step_id": "step-2",
                "order": 2,
                "description": "Add Pydantic validation schema",
                "agent_persona": "coder_be",
                "depends_on": ["step-1"],
                "files_affected": ["backend/app/schemas/user.py"],
            },
            {
                "step_id": "step-3",
                "order": 3,
                "description": "Run tests",
                "agent_persona": "qa",
                "depends_on": ["step-2"],
                "files_affected": [],
            },
        ],
        "estimated_complexity": 4,
        "affected_files": [
            "backend/app/api/users.py",
            "backend/app/schemas/user.py",
        ],
        "risks": ["May break existing API consumers"],
    }


# =============================================================================
# Mock LLM Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""

    def _create_response(
        ui_title: str = "Test Action",
        ui_subtitle: str = "Test subtitle",
        confidence: float = 0.9,
    ) -> dict:
        return {
            "ui_title": ui_title,
            "ui_subtitle": ui_subtitle,
            "technical_reasoning": "Mock LLM reasoning",
            "tool_calls": [],
            "confidence_score": confidence,
            "agent_persona": "planner",
        }

    return _create_response


@pytest.fixture
def mock_planner_response(sample_task_plan_data) -> dict:
    """Mock response from the Planner agent."""
    return {
        "ui_title": "📋 Plan Created: Task Analysis Complete",
        "ui_subtitle": "I've created a 3-step plan to complete your request.",
        "technical_reasoning": str(sample_task_plan_data),
        "tool_calls": [],
        "confidence_score": 0.85,
        "agent_persona": "planner",
    }


@pytest.fixture
def mock_coder_response() -> dict:
    """Mock response from the Coder agent."""
    return {
        "ui_title": "💻 Code Updated: Added Validation",
        "ui_subtitle": "I've added Pydantic validation to the registration endpoint.",
        "technical_reasoning": "Added UserCreate schema with email and password validation.",
        "tool_calls": [
            {
                "tool_name": "edit_file_snippet",
                "arguments": {
                    "path": "backend/app/api/users.py",
                    "old_content": "def register(data: dict):",
                    "new_content": "def register(data: UserCreate):",
                },
                "success": True,
            }
        ],
        "confidence_score": 0.9,
        "agent_persona": "coder_be",
    }


@pytest.fixture
def mock_qa_response() -> dict:
    """Mock response from the QA agent."""
    return {
        "ui_title": "✅ Tests Passed",
        "ui_subtitle": "All tests passed successfully.",
        "technical_reasoning": "Ran pytest, 15 tests passed, 0 failed.",
        "tool_calls": [
            {
                "tool_name": "run_shell_command",
                "arguments": {"command": "pytest"},
                "result": "15 passed",
                "success": True,
            }
        ],
        "confidence_score": 0.95,
        "agent_persona": "qa",
    }


# =============================================================================
# Tool Registry Fixtures
# =============================================================================


@pytest.fixture
def clean_tool_registry():
    """Provide a clean tool registry for testing."""
    from gravity_core.tools.registry import ToolRegistry

    # Store original tools
    original_tools = ToolRegistry._tools.copy()
    original_schemas = ToolRegistry._schemas.copy()

    # Clear registry
    ToolRegistry._tools.clear()
    ToolRegistry._schemas.clear()

    yield ToolRegistry

    # Restore original tools
    ToolRegistry._tools = original_tools
    ToolRegistry._schemas = original_schemas
