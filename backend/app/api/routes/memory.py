"""The user's own view of what the assistant remembers about them.

The AI writes memory through its tools; this router is the human side of the same
table — inspect it, add something the AI missed, correct it, or drop it. Every
query is scoped to the caller, so a memory id from another account reads as 404
rather than leaking a fact or confirming the row exists.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.memory import MEMORY_CATEGORIES
from app.models.user import User
from app.schemas.memory import (
    MemoryContextResponse,
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
    PreferencesResponse,
    SignupPreferences,
    SignupQuestion,
)
from app.services import user_memory

router = APIRouter(prefix="/memory", tags=["Long-Term Memory"])


@router.get("/questions", response_model=List[SignupQuestion])
def get_signup_questions():
    """The sign-up questionnaire, served so the form and the AI agree on it.

    Unauthenticated: the sign-up form has to render it before an account exists.
    """
    return user_memory.SIGNUP_QUESTIONS


@router.get("/categories")
def get_memory_categories():
    """Category -> the heading it appears under in the assistant's prompt."""
    return MEMORY_CATEGORIES


@router.get("", response_model=List[MemoryResponse])
def list_my_memories(
    include_inactive: bool = Query(False, description="Include memories the AI or the user has discarded."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything remembered about the caller."""
    # Reading is also when expiry is applied, so this never shows a row the
    # assistant would already have dropped.
    user_memory.purge_expired(db, current_user.id)
    return user_memory.list_memories(db, current_user.id, include_inactive=include_inactive)


@router.get("/context", response_model=MemoryContextResponse)
def get_my_memory_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The verbatim block the assistant is given on every turn."""
    context = user_memory.build_memory_context(db, current_user.id)
    live = user_memory.active_memories(db, current_user.id)
    return MemoryContextResponse(
        context=context,
        active_count=len(live),
        by_category=user_memory.memory_summary(live),
    )


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_MEMORY)
def create_my_memory(
    request: Request,
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tell the assistant something directly, without going through the chat."""
    try:
        return user_memory.remember(
            db,
            current_user.id,
            content=payload.content,
            category=payload.category,
            source="user",
            expires_in_days=payload.expires_in_days,
        )
    except user_memory.MemoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{memory_id}", response_model=MemoryResponse)
@limiter.limit(settings.RATE_LIMIT_MEMORY)
def update_my_memory(
    request: Request,
    memory_id: int,
    payload: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Correct a remembered fact, or restore one that was discarded."""
    try:
        mem = user_memory.update_memory(
            db,
            current_user.id,
            memory_id,
            content=payload.content,
            category=payload.category,
            active=payload.active,
        )
    except user_memory.MemoryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    return mem


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Make the assistant forget one thing. The row is retired, not deleted."""
    if user_memory.forget(db, current_user.id, memory_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    return None


@router.get("/preferences", response_model=PreferencesResponse)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The structured sign-up answers, plus the memories they produced."""
    live = user_memory.active_memories(db, current_user.id)
    return PreferencesResponse(
        preferences=current_user.preferences or {},
        seeded_memories=[m for m in live if m.source == "signup"],
    )


@router.put("/preferences", response_model=PreferencesResponse)
@limiter.limit(settings.RATE_LIMIT_MEMORY)
def update_my_preferences(
    request: Request,
    payload: SignupPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-answer the sign-up questions later on.

    The answers are merged rather than replaced, so re-submitting one question
    does not erase the others. Re-seeding then updates the derived memories:
    the single-answer categories (tone, task order) replace their old value, and
    a repeated answer refreshes its row instead of duplicating it.
    """
    answers = dict(current_user.preferences or {})
    answers.update(payload.to_dict())
    current_user.preferences = answers
    # JSON columns are replaced wholesale rather than mutated in place, so
    # SQLAlchemy sees the change without needing flag_modified.
    db.commit()

    user_memory.seed_from_signup_answers(db, current_user.id, answers)
    live = user_memory.active_memories(db, current_user.id)
    return PreferencesResponse(
        preferences=answers,
        seeded_memories=[m for m in live if m.source == "signup"],
    )
