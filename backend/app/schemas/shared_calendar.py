from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class SharedCalendarCreate(BaseModel):
    name: str


class SharedCalendarMemberResponse(BaseModel):
    id: int
    user_id: int
    email: Optional[str] = None
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class SharedCalendarResponse(BaseModel):
    id: int
    name: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    members: Optional[List[SharedCalendarMemberResponse]] = None

    class Config:
        from_attributes = True


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class SharedMemoryCreate(BaseModel):
    content: str


class SharedMemoryResponse(BaseModel):
    id: int
    shared_calendar_id: int
    content: str
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
