from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SignupPreferences(BaseModel):
    """Answers to the optional sign-up questions (requirement 2.2).

    Every field is optional: the questions exist to give the AI a head start, and
    skipping them must still produce a usable account. The choice fields are
    Literals so a typo is a 422 here rather than a memory row that reads
    "prefers hard_frist"; the free-text ones are length-capped because they end up
    in a system prompt.
    """

    task_order: Optional[Literal["easy_first", "hard_first", "deadline_first", "no_preference"]] = None
    communication_style: Optional[Literal["brief", "detailed", "encouraging", "direct"]] = None
    study_times: Optional[
        List[Literal["early_morning", "morning", "afternoon", "evening", "late_night"]]
    ] = Field(default=None, max_length=5)
    interests: Optional[List[str]] = Field(default=None, max_length=10)
    goals: Optional[str] = Field(default=None, max_length=300)
    daily_routine: Optional[str] = Field(default=None, max_length=300)

    def to_dict(self) -> Dict[str, Any]:
        """Only the answers actually given, so an untouched form stores nothing."""
        return self.model_dump(exclude_none=True)


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=400)
    category: Optional[str] = None
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=400)
    category: Optional[str] = None
    active: Optional[bool] = None


class MemoryResponse(BaseModel):
    id: int
    user_id: int
    category: str
    content: str
    source: str
    active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryContextResponse(BaseModel):
    """The exact block the assistant is given, so a user can see what it knows."""

    context: str
    active_count: int
    by_category: Dict[str, int]


class SignupQuestionOption(BaseModel):
    value: str
    label: str


class SignupQuestion(BaseModel):
    key: str
    question: str
    type: str
    category: str
    options: Optional[List[SignupQuestionOption]] = None
    placeholder: Optional[str] = None


class PreferencesResponse(BaseModel):
    preferences: Dict[str, Any]
    seeded_memories: List[MemoryResponse]
