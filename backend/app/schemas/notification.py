from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    event_id: Optional[int] = None
    message: str
    read: bool
    created_at: datetime
    event_title: Optional[str] = None

    class Config:
        from_attributes = True
