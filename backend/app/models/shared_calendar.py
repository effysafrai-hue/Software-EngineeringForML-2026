from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class SharedCalendar(Base):
    __tablename__ = "shared_calendars"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
    members = relationship(
        "SharedCalendarMember",
        back_populates="calendar",
        cascade="all, delete-orphan",
    )
    events = relationship(
        "Event",
        back_populates="shared_calendar",
        cascade="all, delete-orphan",
    )
    memories = relationship(
        "SharedMemory",
        back_populates="calendar",
        cascade="all, delete-orphan",
        order_by="SharedMemory.created_at.desc()",
    )
    chat_messages = relationship(
        "ChatMessage",
        back_populates="shared_calendar",
        cascade="all, delete-orphan",
    )


class SharedCalendarMember(Base):
    __tablename__ = "shared_calendar_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    calendar_id = Column(
        Integer,
        ForeignKey("shared_calendars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(50), nullable=False, default="member")  # owner, member
    joined_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("calendar_id", "user_id", name="uq_calendar_user"),
    )

    calendar = relationship("SharedCalendar", back_populates="members")
    user = relationship("User", back_populates="shared_calendar_memberships")


class SharedMemory(Base):
    __tablename__ = "shared_memories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    shared_calendar_id = Column(
        Integer,
        ForeignKey("shared_calendars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    calendar = relationship("SharedCalendar", back_populates="memories")
    author = relationship("User", foreign_keys=[created_by])
