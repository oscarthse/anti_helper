"""
Integration Tests for FastAPI Endpoints

Tests the API endpoints with a test database,
verifying request/response handling and state changes.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from datetime import datetime

# Add project paths
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import app
from backend.app.db.session import get_session


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test the root endpoint returns health status."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test the health endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRepositoryEndpoints:
    """Tests for repository management endpoints."""

    @pytest.fixture
    def mock_db_session(self, db_session, mocker):
        """Override the database session for testing."""
        async def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session
        yield db_session
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_repos_empty(self, mock_db_session):
        """Test listing repos when none exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/repos/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_repo_invalid_path(self, mock_db_session):
        """Test creating a repo with invalid path."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/repos/",
                json={
                    "name": "test-repo",
                    "path": "/nonexistent/path/to/repo",
                },
            )

        assert response.status_code == 400
        assert "not exist" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_repo_not_found(self, mock_db_session):
        """Test getting a non-existent repo."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(f"/api/repos/{uuid4()}")

        assert response.status_code == 404


class TestTaskEndpoints:
    """Tests for task management endpoints."""

    @pytest.fixture
    def mock_db_session(self, db_session, mocker):
        """Override the database session for testing."""
        async def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session
        yield db_session
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, mock_db_session):
        """Test listing tasks when none exist."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/tasks/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_task_repo_not_found(self, mock_db_session):
        """Test creating a task with non-existent repo."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/tasks/",
                json={
                    "repo_id": str(uuid4()),
                    "user_request": "Add validation to the user endpoint",
                },
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_task_request_too_short(self, mock_db_session):
        """Test that short requests are rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/tasks/",
                json={
                    "repo_id": str(uuid4()),
                    "user_request": "Short",  # Less than 10 chars
                },
            )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, mock_db_session):
        """Test getting a non-existent task."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(f"/api/tasks/{uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, mock_db_session):
        """Test cancelling a non-existent task."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(f"/api/tasks/{uuid4()}/cancel")

        assert response.status_code == 404


class TestTaskWithRepository:
    """Tests for task operations with existing repository."""

    @pytest_asyncio.fixture
    async def repo_with_task(self, db_session, mocker):
        """Create a repository and task for testing."""
        from backend.app.db.models import Repository, Task, TaskStatus

        # Create repository
        repo = Repository(
            id=uuid4(),
            name="test-repo",
            path="/tmp",  # Use /tmp which exists
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(repo)
        await db_session.flush()

        # Create task
        task = Task(
            id=uuid4(),
            repo_id=repo.id,
            user_request="Test task with sufficient length",
            status=TaskStatus.PENDING,
            current_step=0,
            retry_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.flush()

        # Override session
        async def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session

        yield {"repo": repo, "task": task}

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_task_success(self, repo_with_task):
        """Test getting an existing task."""
        task = repo_with_task["task"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(f"/api/tasks/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(task.id)
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_execute_task(self, repo_with_task):
        """Test triggering task execution."""
        task = repo_with_task["task"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(f"/api/tasks/{task.id}/execute")

        assert response.status_code == 200
        assert "started" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self, repo_with_task):
        """Test cancelling a pending task."""
        task = repo_with_task["task"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(f"/api/tasks/{task.id}/cancel")

        assert response.status_code == 200
        assert "cancelled" in response.json()["message"].lower()
