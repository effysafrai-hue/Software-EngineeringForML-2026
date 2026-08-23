from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
