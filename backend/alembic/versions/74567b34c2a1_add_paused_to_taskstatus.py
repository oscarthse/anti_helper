"""add paused to taskstatus

Revision ID: 74567b34c2a1
Revises: 5803305ba5cd
Create Date: 2025-12-08 03:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74567b34c2a1'
down_revision: Union[str, None] = '5803305ba5cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres specific command to add value to enum
    # Alembic doesn't auto-generate this for Enums
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE taskstatus ADD VALUE 'PAUSED'")


def downgrade() -> None:
    # Downgrading enum values in Postgres is complex and usually
    # involves creating a new type, swapping, etc.
    # For now, we will leave the value as it's harmless.
    pass
