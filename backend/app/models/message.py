from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship

from app.db.session import Base


class Message(Base):
    """A direct message between exactly two users.

    There is no conversation/thread table: a conversation is derived as every
    message where the pair {sender_id, receiver_id} matches. That keeps sending
    a single INSERT with no thread bookkeeping, at the cost of an OR-filter on
    read, which the composite indexes below cover.
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    media_urls = Column(JSON, nullable=False, default=list)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_messages_sender_receiver", "sender_id", "receiver_id", "created_at"),
        Index("ix_messages_receiver_sender", "receiver_id", "sender_id", "created_at"),
    )

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
