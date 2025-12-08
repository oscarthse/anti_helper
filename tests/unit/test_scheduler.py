
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Task, Repository, TaskStatus, TaskDependency
from backend.app.services.scheduler import SchedulerService

@pytest.mark.asyncio
async def test_scheduler_dependency_resolution(db_session: AsyncSession):
    """
    Verify get_next_executable_tasks returns ONLY unblocked tasks.

    Graph Structure:
    [A] (No deps)
    [B] (Depends on A)
    [C] (Depends on A)
    [D] (Depends on B and C)

    Scenario 1: All Pending. Expected: [A]
    Scenario 2: A Complete. Expected: [B, C]
    Scenario 3: A, B Complete. Expected: [C] (D is still blocked by C)
    Scenario 4: A, B, C Complete. Expected: [D]
    """
    repo_id = uuid4()
    repo = Repository(id=repo_id, name="TestRepo", path="/tmp/testrepo")
    db_session.add(repo)

    # Root Task
    root = Task(
        id=uuid4(), repo_id=repo_id, user_request="Root", status=TaskStatus.EXECUTING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    db_session.add(root)
    await db_session.flush()

    # Create Subtasks
    task_a = Task(id=uuid4(), repo_id=repo_id, parent_task_id=root.id, title="A", status=TaskStatus.PENDING, user_request="A", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    task_b = Task(id=uuid4(), repo_id=repo_id, parent_task_id=root.id, title="B", status=TaskStatus.PENDING, user_request="B", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    task_c = Task(id=uuid4(), repo_id=repo_id, parent_task_id=root.id, title="C", status=TaskStatus.PENDING, user_request="C", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    task_d = Task(id=uuid4(), repo_id=repo_id, parent_task_id=root.id, title="D", status=TaskStatus.PENDING, user_request="D", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    db_session.add_all([task_a, task_b, task_c, task_d])
    await db_session.flush()

    # Create Dependencies
    # B needs A
    dep_b_a = TaskDependency(blocker_task_id=task_a.id, blocked_task_id=task_b.id)
    # C needs A
    dep_c_a = TaskDependency(blocker_task_id=task_a.id, blocked_task_id=task_c.id)
    # D needs B AND C
    dep_d_b = TaskDependency(blocker_task_id=task_b.id, blocked_task_id=task_d.id)
    dep_d_c = TaskDependency(blocker_task_id=task_c.id, blocked_task_id=task_d.id)

    db_session.add_all([dep_b_a, dep_c_a, dep_d_b, dep_d_c])
    await db_session.commit()

    scheduler = SchedulerService(db_session)

    # --- Scenario 1: All Pending ---
    # Only A has no dependencies
    ready = await scheduler.get_next_executable_tasks(root.id)
    ready_titles = {t.title for t in ready}
    assert ready_titles == {"A"}, f"Expected {{'A'}}, got {ready_titles}"

    # --- Scenario 2: A Complete ---
    task_a.status = TaskStatus.COMPLETED
    await db_session.commit()

    ready = await scheduler.get_next_executable_tasks(root.id)
    ready_titles = {t.title for t in ready}
    # A is done, so B and C should be unblocked. D is blocked by B and C. A is not pending.
    assert ready_titles == {"B", "C"}, f"Expected {{'B', 'C'}}, got {ready_titles}"

    # --- Scenario 3: B Complete ---
    task_b.status = TaskStatus.COMPLETED
    await db_session.commit()

    ready = await scheduler.get_next_executable_tasks(root.id)
    ready_titles = {t.title for t in ready}
    # C is still pending and unblocked. D is blocked by C.
    assert ready_titles == {"C"}, f"Expected {{'C'}}, got {ready_titles}"

    # --- Scenario 4: C Complete ---
    task_c.status = TaskStatus.COMPLETED
    await db_session.commit()

    ready = await scheduler.get_next_executable_tasks(root.id)
    ready_titles = {t.title for t in ready}
    # D is now unblocked
    assert ready_titles == {"D"}, f"Expected {{'D'}}, got {ready_titles}"
