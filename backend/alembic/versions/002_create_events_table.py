"""create events table

Revision ID: 002_create_events_table
Revises: 001_create_users_table
Create Date: 2026-08-23 21:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_create_events_table"
down_revision: Union[str, None] = "001_create_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_id"), "events", ["id"], unique=False)
    op.create_index(op.f("ix_events_user_id"), "events", ["user_id"], unique=False)
    op.create_index(op.f("ix_events_start_time"), "events", ["start_time"], unique=False)
    op.create_index(op.f("ix_events_end_time"), "events", ["end_time"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_events_end_time"), table_name="events")
    op.drop_index(op.f("ix_events_start_time"), table_name="events")
    op.drop_index(op.f("ix_events_user_id"), table_name="events")
    op.drop_index(op.f("ix_events_id"), table_name="events")
    op.drop_table("events")
