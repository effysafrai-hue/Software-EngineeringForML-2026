from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import (
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    serialize_message,
)
from app.services import realtime
from app.services.sanitize import sanitize_user_text, validate_media_urls

router = APIRouter(tags=["Direct Messages"])


def _conversation_filter(user_a: int, user_b: int):
    """Every message exchanged between two users, in either direction."""
    return or_(
        and_(Message.sender_id == user_a, Message.receiver_id == user_b),
        and_(Message.sender_id == user_b, Message.receiver_id == user_a),
    )


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_MESSAGE)
def send_message(
    request: Request,
    message_in: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a direct message to another user."""
    if message_in.receiver_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot send a direct message to yourself.",
        )

    receiver = db.query(User).filter(User.id == message_in.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        body=sanitize_user_text(message_in.body, field="body"),
        media_urls=validate_media_urls(message_in.media_urls),
        read=False,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    payload = serialize_message(message)
    payload["created_at"] = message.created_at.isoformat()

    # Addressed to one person, so never broadcast: the frame goes to the
    # recipient only, and the sender's other open tabs.
    realtime.push_to_user(
        current_user.id,
        {"type": realtime.EVENT_NEW_MESSAGE, "message_data": payload},
    )
    realtime.notify_user(
        db,
        user_id=receiver.id,
        actor_id=current_user.id,
        message=f"New message from {current_user.email}.",
        payload={"type": realtime.EVENT_NEW_MESSAGE, "message_data": payload},
    )

    return serialize_message(message)


@router.get("/messages/{other_user_id}", response_model=ConversationResponse)
def get_conversation(
    other_user_id: int,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read the thread between the caller and one other user.

    The filter is anchored to `current_user.id` on both sides, so there is no
    parameter a third party could pass to see someone else's thread: asking for
    /messages/{X} always returns *your* conversation with X.
    """
    other = db.query(User).filter(User.id == other_user_id).first()
    if not other:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    convo_filter = _conversation_filter(current_user.id, other_user_id)
    messages = (
        db.query(Message)
        .filter(convo_filter)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    unread_count = (
        db.query(Message)
        .filter(
            Message.sender_id == other_user_id,
            Message.receiver_id == current_user.id,
            Message.read == False,  # noqa: E712 - SQL comparison, not a Python bool test
        )
        .count()
    )

    return {
        "peer_id": other_user_id,
        "peer_email": other.email,
        "unread_count": unread_count,
        "messages": [serialize_message(m) for m in messages],
    }


@router.post("/messages/{other_user_id}/read", status_code=status.HTTP_200_OK)
def mark_conversation_read(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark every message received from one user as read.

    Kept as an explicit call rather than a side effect of GET, so reading a
    conversation stays idempotent and a preview does not silently clear the
    sender's unread badge.
    """
    updated = (
        db.query(Message)
        .filter(
            Message.sender_id == other_user_id,
            Message.receiver_id == current_user.id,
            Message.read == False,  # noqa: E712
        )
        .update({"read": True}, synchronize_session=False)
    )
    db.commit()
    return {"message": f"Marked {updated} message(s) as read.", "updated": updated}
