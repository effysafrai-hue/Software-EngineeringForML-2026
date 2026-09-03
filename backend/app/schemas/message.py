from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    receiver_id: int
    body: str = Field(..., min_length=1)
    media_urls: List[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    body: str
    media_urls: List[str] = []
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """A full two-party thread, oldest first."""

    peer_id: int
    peer_email: Optional[str] = None
    unread_count: int = 0
    messages: List[MessageResponse] = []


def serialize_message(message) -> dict:
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "body": message.body,
        "media_urls": message.media_urls or [],
        "read": bool(message.read),
        "created_at": message.created_at,
    }
