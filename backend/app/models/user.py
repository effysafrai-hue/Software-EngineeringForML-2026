from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    preferences = Column(JSON, nullable=True, default=dict)

    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan"
    )
    shared_calendar_memberships = relationship(
        "SharedCalendarMember", back_populates="user", cascade="all, delete-orphan"
    )
    memories = relationship(
        "UserMemory", back_populates="user", cascade="all, delete-orphan"
    )
