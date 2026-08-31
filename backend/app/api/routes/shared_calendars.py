import re
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.event import Event
from app.models.chat import ChatMessage
from app.models.shared_calendar import SharedCalendar, SharedCalendarMember, SharedMemory
from app.schemas.event import EventCreate, EventResponse, EventUpdate
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessageResponse
from app.schemas.shared_calendar import (
    SharedCalendarCreate,
    SharedCalendarResponse,
    SharedCalendarMemberResponse,
    AddMemberRequest,
    SharedMemoryCreate,
    SharedMemoryResponse,
)
from app.services.ai_agent import process_chat
from app.services.chat_queue import chat_queue, Priority

router = APIRouter(prefix="/shared-calendars", tags=["Shared Calendars"])


def get_calendar_member_or_403(calendar_id: int, user_id: int, db: Session) -> SharedCalendarMember:
    member = (
        db.query(SharedCalendarMember)
        .filter(
            SharedCalendarMember.calendar_id == calendar_id,
            SharedCalendarMember.user_id == user_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this shared calendar.",
        )
    return member


@router.post("", response_model=SharedCalendarResponse, status_code=status.HTTP_201_CREATED)
def create_shared_calendar(
    payload: SharedCalendarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new shared calendar. Creator is automatically added as owner."""
    cal = SharedCalendar(name=payload.name, created_by=current_user.id)
    db.add(cal)
    db.commit()
    db.refresh(cal)

    # Add creator as owner member
    owner_member = SharedCalendarMember(
        calendar_id=cal.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(owner_member)
    db.commit()
    db.refresh(cal)

    return cal


@router.get("", response_model=List[SharedCalendarResponse])
def list_my_shared_calendars(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all shared calendars the current user belongs to."""
    memberships = (
        db.query(SharedCalendarMember)
        .filter(SharedCalendarMember.user_id == current_user.id)
        .all()
    )
    cal_ids = [m.calendar_id for m in memberships]
    cals = db.query(SharedCalendar).filter(SharedCalendar.id.in_(cal_ids)).all()
    return cals


@router.get("/{calendar_id}", response_model=SharedCalendarResponse)
def get_shared_calendar_details(
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get shared calendar details and member list (members only)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)
    cal = db.query(SharedCalendar).filter(SharedCalendar.id == calendar_id).first()
    if not cal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar not found.")

    res = SharedCalendarResponse(
        id=cal.id,
        name=cal.name,
        created_by=cal.created_by,
        created_at=cal.created_at,
        updated_at=cal.updated_at,
        members=[
            SharedCalendarMemberResponse(
                id=m.id,
                user_id=m.user_id,
                email=m.user.email if m.user else None,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m in cal.members
        ],
    )
    return res


@router.post("/{calendar_id}/members", status_code=status.HTTP_201_CREATED)
def add_member_to_shared_calendar(
    calendar_id: int,
    payload: AddMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a member to the shared calendar by email (members only)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    target_user = db.query(User).filter(User.email == payload.email).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User with this email not found.")

    existing = (
        db.query(SharedCalendarMember)
        .filter(
            SharedCalendarMember.calendar_id == calendar_id,
            SharedCalendarMember.user_id == target_user.id,
        )
        .first()
    )
    if existing:
        return {"message": "User is already a member."}

    new_member = SharedCalendarMember(
        calendar_id=calendar_id,
        user_id=target_user.id,
        role=payload.role,
    )
    db.add(new_member)
    db.commit()
    return {"message": f"User {payload.email} added to calendar."}


# Shared Events CRUD
@router.get("/{calendar_id}/events", response_model=List[EventResponse])
def list_shared_calendar_events(
    calendar_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List events for a shared calendar (members only)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    query = db.query(Event).filter(Event.shared_calendar_id == calendar_id)
    if start_time:
        query = query.filter(Event.end_time >= start_time)
    if end_time:
        query = query.filter(Event.start_time <= end_time)

    return query.order_by(Event.start_time.asc()).all()


@router.post("/{calendar_id}/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_shared_calendar_event(
    calendar_id: int,
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an event on a shared calendar (any member can create)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    event = Event(
        user_id=current_user.id,
        shared_calendar_id=calendar_id,
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{calendar_id}/events/{event_id}", response_model=EventResponse)
def update_shared_calendar_event(
    calendar_id: int,
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a shared calendar event (any member can edit)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.shared_calendar_id == calendar_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found on this shared calendar.")

    update_data = event_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(event, field, val)

    db.commit()
    db.refresh(event)
    return event


@router.delete("/{calendar_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shared_calendar_event(
    calendar_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a shared calendar event (any member can delete)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.shared_calendar_id == calendar_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found on this shared calendar.")

    db.delete(event)
    db.commit()
    return None


# Shared Memories
@router.get("/{calendar_id}/memories", response_model=List[SharedMemoryResponse])
def list_shared_memories(
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List shared memories/rules for this calendar (all members can view)."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)
    memories = (
        db.query(SharedMemory)
        .filter(SharedMemory.shared_calendar_id == calendar_id)
        .order_by(SharedMemory.created_at.desc())
        .all()
    )
    return memories


@router.post("/{calendar_id}/memories", response_model=SharedMemoryResponse, status_code=status.HTTP_201_CREATED)
def create_shared_memory(
    calendar_id: int,
    payload: SharedMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a shared memory/context rule for this calendar group."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    mem = SharedMemory(
        shared_calendar_id=calendar_id,
        content=payload.content,
        created_by=current_user.id,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


# Scoped Shared Chat
@router.post("/{calendar_id}/chat", response_model=ChatResponse)
async def send_shared_chat_message(
    calendar_id: int,
    chat_req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI Assistant scoped to this shared calendar.
    Messages and derived memories are persisted and visible to all members.
    """
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    if not chat_req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty",
        )

    # 1. Record user message with shared_calendar_id
    user_msg = ChatMessage(
        user_id=current_user.id,
        shared_calendar_id=calendar_id,
        role="user",
        content=chat_req.message,
    )
    db.add(user_msg)
    db.commit()

    # 2. Check if user is establishing a group preference / memory
    # E.g. "this group meets Tuesdays, avoid scheduling then" or "remember that our team prefers morning syncs"
    msg_lower = chat_req.message.lower()
    if any(k in msg_lower for k in ["meets tuesdays", "avoid scheduling", "remember that this group", "our team prefers", "group rule", "always keep in mind"]):
        # Extract and persist as shared memory
        clean_content = chat_req.message
        # Strip conversational prefixes if present
        m = re.search(r"(?:remember that|note that|keep in mind that)\s+(.*)", chat_req.message, re.IGNORECASE)
        if m:
            clean_content = m.group(1).strip()

        shared_mem = SharedMemory(
            shared_calendar_id=calendar_id,
            content=clean_content,
            created_by=current_user.id,
        )
        db.add(shared_mem)
        db.commit()

    # 3. Process AI response
    # Retrieve existing group memories to provide as context
    existing_memories = (
        db.query(SharedMemory)
        .filter(SharedMemory.shared_calendar_id == calendar_id)
        .all()
    )
    memory_context = ""
    if existing_memories:
        memory_lines = [f"- {m.content}" for m in existing_memories]
        memory_context = f"\n[SHARED GROUP MEMORIES & CONSTRAINTS]:\n" + "\n".join(memory_lines) + "\n"

    enriched_prompt = chat_req.message
    if memory_context:
        enriched_prompt = f"{chat_req.message}\n{memory_context}"

    ai_result = await chat_queue.submit(
        Priority.SHARED_CALENDAR_CHAT,
        process_chat,
        message=enriched_prompt,
        user_id=current_user.id,
        db=db,
    )

    # If an event was created, associate it with the shared calendar
    if ai_result.get("action_taken") == "create_event":
        latest_event = (
            db.query(Event)
            .filter(Event.user_id == current_user.id)
            .order_by(Event.id.desc())
            .first()
        )
        if latest_event and latest_event.shared_calendar_id is None:
            latest_event.shared_calendar_id = calendar_id
            db.commit()

    # 4. Record assistant message with shared_calendar_id
    assistant_msg = ChatMessage(
        user_id=current_user.id,
        shared_calendar_id=calendar_id,
        role="assistant",
        content=ai_result["reply"],
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        reply=ai_result["reply"],
        action_taken=ai_result.get("action_taken"),
    )


@router.get("/{calendar_id}/chat/history", response_model=List[ChatMessageResponse])
def get_shared_chat_history(
    calendar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve shared chat message history visible to all calendar members."""
    get_calendar_member_or_403(calendar_id, current_user.id, db)

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.shared_calendar_id == calendar_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages
