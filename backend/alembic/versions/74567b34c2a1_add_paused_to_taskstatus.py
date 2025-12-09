"""add paused to taskstatus

Revision ID: 74567b34c2a1
Revises: 5803305ba5cd
Create Date: 2025-12-08 03:52:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74567b34c2a1"
down_revision: str | None = "5803305ba5cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres specific command to add value to enum
    # Alembic doesn't auto-generate this for Enums
    with op.get_context().autocommit_block():
        try:
            op.execute("ALTER TYPE taskstatus ADD VALUE 'PAUSED'")
        except Exception as e:
            if "already exists" in str(e):
                print("Enum value 'PAUSED' already exists, skipping.")
            else:
                raise


def downgrade() -> None:
    # Downgrading enum values in Postgres is complex and usually
    # involves creating a new type, swapping, etc.
    # For now, we will leave the value as it's harmless.
    pass
