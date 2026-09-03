"""create user_memories table for per-user long-term memory

Revision ID: 009_user_memories
Revises: 008_reactions_and_messages
Create Date: 2026-09-03 21:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009_user_memories"
down_revision: Union[str, None] = "008_reactions_and_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="ai"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_memories_id"), "user_memories", ["id"], unique=False)
    op.create_index(op.f("ix_user_memories_user_id"), "user_memories", ["user_id"], unique=False)
    # Every read of a user's memory filters on both columns (the prompt only ever
    # wants the live rows), so they are indexed together.
    op.create_index("ix_user_memories_user_active", "user_memories", ["user_id", "active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_memories_user_active", table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_user_id"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_id"), table_name="user_memories")
    op.drop_table("user_memories")
