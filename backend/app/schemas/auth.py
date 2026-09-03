from datetime import datetime
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.memory import SignupPreferences


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str
    # Optional answers to the sign-up questions (requirement 2.2). They are
    # seeded into long-term memory so the assistant is personal from the first
    # message; leaving them out is a normal sign-up.
    preferences: Optional[SignupPreferences] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"\d", v) and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError(
                "Password must contain at least one number or special character"
            )
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime
    preferences: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
