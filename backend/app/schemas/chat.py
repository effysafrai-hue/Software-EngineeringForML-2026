from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    reply: str
    action_taken: Optional[str] = None
    # What the assistant decided to keep or drop from long-term memory on this
    # turn. Surfaced so the user can see the decision instead of discovering it
    # in a later reply.
    memory_actions: List[Dict[str, Any]] = Field(default_factory=list)
