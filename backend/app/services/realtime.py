"""Notification + live-push helpers for forum and direct-message activity.

Two distinct things happen when something noteworthy occurs:

* a durable `Notification` row for the one person it concerns, so it survives a
  disconnect and shows up in GET /notifications; and
* a transient WebSocket frame so open clients redraw without a refresh.

Both are best-effort with respect to the request that triggered them — a failed
push must not roll back the comment that caused it.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.services.ws_manager import manager

logger = logging.getLogger("realtime")

# Frame types the frontend switches on.
EVENT_NEW_POST = "forum.post.created"
EVENT_NEW_COMMENT = "forum.comment.created"
EVENT_REACTION = "forum.reaction.changed"
EVENT_NEW_MESSAGE = "dm.message.created"


def push_to_user(user_id: Optional[int], payload: Dict[str, Any]) -> None:
    """Send a frame to one user. Never raises."""
    if not user_id:
        return
    try:
        manager.send_to_user_sync(user_id, payload)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"WebSocket push to user {user_id} failed: {e}")


def broadcast(payload: Dict[str, Any], exclude_user_id: Optional[int] = None) -> None:
    """Send a frame to every connected user. Never raises.

    Only for content that is already public through the REST API, and only with
    the same anonymity masking the API applies.
    """
    try:
        manager.broadcast_sync(payload, exclude_user_id=exclude_user_id)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"WebSocket broadcast failed: {e}")


def notify_user(
    db: Session,
    user_id: Optional[int],
    actor_id: Optional[int],
    message: str,
    payload: Dict[str, Any],
) -> Optional[Notification]:
    """Record a notification for `user_id` and push it live.

    Returns None without writing anything when there is nobody to notify, or
    when the actor is the recipient: nobody wants a notification telling them
    they liked their own post.
    """
    if not user_id or user_id == actor_id:
        return None

    notification = Notification(user_id=user_id, event_id=None, message=message, read=False)
    db.add(notification)
    db.commit()
    db.refresh(notification)

    push_to_user(
        user_id,
        {
            **payload,
            "notification_id": notification.id,
            "message": message,
            "read": False,
        },
    )
    return notification
