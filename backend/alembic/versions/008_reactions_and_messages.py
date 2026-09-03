"""create forum reactions and direct message tables

Revision ID: 008_reactions_and_messages
Revises: 007_forum
Create Date: 2026-09-03 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_reactions_and_messages"
down_revision: Union[str, None] = "007_forum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("comment_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.String(length=7), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # One reaction per user per item. NULLs are distinct, so each constraint
        # only binds the rows that target that kind of item.
        sa.UniqueConstraint("user_id", "post_id", name="uq_reaction_user_post"),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_reaction_user_comment"),
        sa.CheckConstraint(
            "(post_id IS NOT NULL) <> (comment_id IS NOT NULL)",
            name="ck_reaction_exactly_one_target",
        ),
        sa.CheckConstraint("value IN ('like', 'dislike')", name="ck_reaction_value"),
    )
    op.create_index(op.f("ix_reactions_id"), "reactions", ["id"], unique=False)
    op.create_index(op.f("ix_reactions_user_id"), "reactions", ["user_id"], unique=False)
    op.create_index(op.f("ix_reactions_post_id"), "reactions", ["post_id"], unique=False)
    op.create_index(op.f("ix_reactions_comment_id"), "reactions", ["comment_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
    op.create_index(op.f("ix_messages_sender_id"), "messages", ["sender_id"], unique=False)
    op.create_index(op.f("ix_messages_receiver_id"), "messages", ["receiver_id"], unique=False)
    op.create_index(op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False)
    # A conversation is read in both directions, so both orderings get an index.
    op.create_index(
        "ix_messages_sender_receiver", "messages", ["sender_id", "receiver_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_messages_receiver_sender", "messages", ["receiver_id", "sender_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_messages_receiver_sender", table_name="messages")
    op.drop_index("ix_messages_sender_receiver", table_name="messages")
    op.drop_index(op.f("ix_messages_created_at"), table_name="messages")
    op.drop_index(op.f("ix_messages_receiver_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_sender_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_reactions_comment_id"), table_name="reactions")
    op.drop_index(op.f("ix_reactions_post_id"), table_name="reactions")
    op.drop_index(op.f("ix_reactions_user_id"), table_name="reactions")
    op.drop_index(op.f("ix_reactions_id"), table_name="reactions")
    op.drop_table("reactions")
