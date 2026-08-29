"""create shared_calendars, shared_calendar_members, and shared_memories tables

Revision ID: 005_shared_calendars
Revises: 004_courses_and_reviews
Create Date: 2026-08-28 17:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_shared_calendars"
down_revision: Union[str, None] = "004_courses_and_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create shared_calendars table
    op.create_table(
        "shared_calendars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shared_calendars_id"), "shared_calendars", ["id"], unique=False)
    op.create_index(op.f("ix_shared_calendars_created_by"), "shared_calendars", ["created_by"], unique=False)

    # 2. Create shared_calendar_members table
    op.create_table(
        "shared_calendar_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("calendar_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["calendar_id"], ["shared_calendars.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calendar_id", "user_id", name="uq_calendar_user"),
    )
    op.create_index(op.f("ix_shared_calendar_members_id"), "shared_calendar_members", ["id"], unique=False)
    op.create_index(op.f("ix_shared_calendar_members_calendar_id"), "shared_calendar_members", ["calendar_id"], unique=False)
    op.create_index(op.f("ix_shared_calendar_members_user_id"), "shared_calendar_members", ["user_id"], unique=False)

    # 3. Create shared_memories table
    op.create_table(
        "shared_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shared_calendar_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["shared_calendar_id"], ["shared_calendars.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shared_memories_id"), "shared_memories", ["id"], unique=False)
    op.create_index(op.f("ix_shared_memories_shared_calendar_id"), "shared_memories", ["shared_calendar_id"], unique=False)

    # 4. Add shared_calendar_id to events table
    op.add_column("events", sa.Column("shared_calendar_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_events_shared_calendar_id"), "events", ["shared_calendar_id"], unique=False)
    op.create_foreign_key(
        "fk_events_shared_calendar_id",
        "events",
        "shared_calendars",
        ["shared_calendar_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. Add shared_calendar_id to chat_messages table
    op.add_column("chat_messages", sa.Column("shared_calendar_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_chat_messages_shared_calendar_id"), "chat_messages", ["shared_calendar_id"], unique=False)
    op.create_foreign_key(
        "fk_chat_messages_shared_calendar_id",
        "chat_messages",
        "shared_calendars",
        ["shared_calendar_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_messages_shared_calendar_id", "chat_messages", type_="foreignkey")
    op.drop_index(op.f("ix_chat_messages_shared_calendar_id"), table_name="chat_messages")
    op.drop_column("chat_messages", "shared_calendar_id")

    op.drop_constraint("fk_events_shared_calendar_id", "events", type_="foreignkey")
    op.drop_index(op.f("ix_events_shared_calendar_id"), table_name="events")
    op.drop_column("events", "shared_calendar_id")

    op.drop_index(op.f("ix_shared_memories_shared_calendar_id"), table_name="shared_memories")
    op.drop_index(op.f("ix_shared_memories_id"), table_name="shared_memories")
    op.drop_table("shared_memories")

    op.drop_index(op.f("ix_shared_calendar_members_user_id"), table_name="shared_calendar_members")
    op.drop_index(op.f("ix_shared_calendar_members_calendar_id"), table_name="shared_calendar_members")
    op.drop_index(op.f("ix_shared_calendar_members_id"), table_name="shared_calendar_members")
    op.drop_table("shared_calendar_members")

    op.drop_index(op.f("ix_shared_calendars_created_by"), table_name="shared_calendars")
    op.drop_index(op.f("ix_shared_calendars_id"), table_name="shared_calendars")
    op.drop_table("shared_calendars")
