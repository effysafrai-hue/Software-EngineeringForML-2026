"""create courses and reviews table

Revision ID: 004_courses_and_reviews
Revises: 003_create_chat_messages_table
Create Date: 2026-08-28 16:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_courses_and_reviews"
down_revision: Union[str, None] = "003_create_chat_messages_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    has_vector = False

    if conn.dialect.name == "postgresql":
        try:
            res = conn.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).scalar()
            if res:
                conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
                has_vector = True
        except Exception:
            has_vector = False

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("syllabus_topics", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_courses_id"), "courses", ["id"], unique=False)
    op.create_index(op.f("ix_courses_code"), "courses", ["code"], unique=True)

    if conn.dialect.name == "postgresql" and has_vector:
        try:
            op.execute("ALTER TABLE courses DROP COLUMN embedding;")
            op.execute("ALTER TABLE courses ADD COLUMN embedding vector(768);")
        except Exception:
            pass

    op.create_table(
        "course_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_course_reviews_id"), "course_reviews", ["id"], unique=False)
    op.create_index(op.f("ix_course_reviews_course_id"), "course_reviews", ["course_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_course_reviews_course_id"), table_name="course_reviews")
    op.drop_index(op.f("ix_course_reviews_id"), table_name="course_reviews")
    op.drop_table("course_reviews")
    op.drop_index(op.f("ix_courses_code"), table_name="courses")
    op.drop_index(op.f("ix_courses_id"), table_name="courses")
    op.drop_table("courses")
