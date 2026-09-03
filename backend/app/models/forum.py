from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base

REACTION_LIKE = "like"
REACTION_DISLIKE = "dislike"
REACTION_VALUES = (REACTION_LIKE, REACTION_DISLIKE)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    media_urls = Column(JSON, nullable=False, default=list)
    anonymous = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User")
    comments = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Comment.created_at.asc()",
    )
    reactions = relationship(
        "Reaction",
        back_populates="post",
        cascade="all, delete-orphan",
        foreign_keys="Reaction.post_id",
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    media_urls = Column(JSON, nullable=False, default=list)
    anonymous = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User")
    post = relationship("Post", back_populates="comments")
    reactions = relationship(
        "Reaction",
        back_populates="comment",
        cascade="all, delete-orphan",
        foreign_keys="Reaction.comment_id",
    )


class Reaction(Base):
    """A single like/dislike by one user on either a post or a comment.

    One row per (user, item): changing your mind updates `value` in place rather
    than accumulating rows, which is what keeps the counts a plain COUNT(*).
    """

    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    value = Column(String(7), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # NULLs compare as distinct, so each of these only constrains the rows
        # that actually target that kind of item: post reactions have a NULL
        # comment_id and vice versa.
        UniqueConstraint("user_id", "post_id", name="uq_reaction_user_post"),
        UniqueConstraint("user_id", "comment_id", name="uq_reaction_user_comment"),
        CheckConstraint(
            "(post_id IS NOT NULL) <> (comment_id IS NOT NULL)",
            name="ck_reaction_exactly_one_target",
        ),
        CheckConstraint("value IN ('like', 'dislike')", name="ck_reaction_value"),
    )

    user = relationship("User")
    post = relationship("Post", back_populates="reactions", foreign_keys=[post_id])
    comment = relationship("Comment", back_populates="reactions", foreign_keys=[comment_id])
