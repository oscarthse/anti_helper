from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Repository, Task, TaskStatus
from backend.app.services.blackboard import BlackboardService


@pytest.mark.asyncio
async def test_blackboard_scope_resolution(db_session: AsyncSession):
    """
    Verify that get_context correctly resolves inheritance:
    Root (Theme=Dark) -> Child (Language=EN) -> Grandchild (Theme=Light)

    Expected for Grandchild: Theme=Light, Language=EN.
    """
    # 1. Setup Data hierarchy
    repo_id = uuid4()
    repo = Repository(id=repo_id, name="TestRepo", path="/tmp/testrepo")
    db_session.add(repo)

    # Root Task
    root = Task(
        id=uuid4(),
        repo_id=repo_id,
        user_request="Root",
        status=TaskStatus.PLANNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(root)

    # Child Task
    child = Task(
        id=uuid4(),
        repo_id=repo_id,
        parent_task_id=root.id,
        user_request="Child",
        status=TaskStatus.PLANNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(child)

    # Grandchild Task
    grandchild = Task(
        id=uuid4(),
        repo_id=repo_id,
        parent_task_id=child.id,
        user_request="Grandchild",
        status=TaskStatus.PLANNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(grandchild)

    await db_session.commit()

    # 2. Populate Knowledge
    service = BlackboardService(db_session)

    # Root sets Theme=Dark
    await service.add_knowledge(root.id, "theme", {"mode": "dark"})

    # Child sets Language=EN
    await service.add_knowledge(child.id, "language", {"code": "en"})

    # Grandchild overrides Theme=Light
    await service.add_knowledge(grandchild.id, "theme", {"mode": "light"})

    # 3. Verify Contexts

    # Root Context
    root_ctx = await service.get_context(root.id)
    assert root_ctx["theme"] == {"mode": "dark"}
    assert "language" not in root_ctx

    # Child Context (Inherits Theme, Defines Language)
    child_ctx = await service.get_context(child.id)
    assert child_ctx["theme"] == {"mode": "dark"}
    assert child_ctx["language"] == {"code": "en"}

    # Grandchild Context (Overrides Theme, Inherits Language)
    grandchild_ctx = await service.get_context(grandchild.id)
    assert grandchild_ctx["theme"] == {"mode": "light"}  # OVERRIDE
    assert grandchild_ctx["language"] == {"code": "en"}  # INHERIT
