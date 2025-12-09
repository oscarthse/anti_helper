"""Add Phase 1 Quality columns to Task

Revision ID: 0f66ef656a68
Revises: 74567b34c2a1
Create Date: 2025-12-08 20:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f66ef656a68"
down_revision: str | None = "74567b34c2a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("files_changed_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "tasks", sa.Column("fix_attempts_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("tasks", sa.Column("tests_run_command", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("tests_exit_code", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "tests_exit_code")
    op.drop_column("tasks", "tests_run_command")
    op.drop_column("tasks", "fix_attempts_count")
    op.drop_column("tasks", "files_changed_count")
