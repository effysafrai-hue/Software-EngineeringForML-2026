"""add users.timezone for wall-clock scheduling

Revision ID: 010_user_timezone
Revises: 009_user_memories
Create Date: 2026-09-03 23:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010_user_timezone"
down_revision: Union[str, None] = "009_user_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with no default: "we have not heard from this user's browser yet"
    # has to be distinguishable from "this user is in UTC", because the first
    # falls back to DEFAULT_TIMEZONE and the second does not.
    op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "timezone")
