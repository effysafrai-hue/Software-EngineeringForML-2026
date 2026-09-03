import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import decode_jwt_token
from app.db.session import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.services.ws_manager import manager

logger = logging.getLogger("notifications")

router = APIRouter(tags=["Notifications"])


@router.get("/notifications", response_model=List[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.read == False)
    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()

    result = []
    for n in notifications:
        event_title = n.event.title if n.event else None
        result.append(NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            event_id=n.event_id,
            message=n.message,
            read=n.read,
            created_at=n.created_at,
            event_title=event_title,
        ))
    return result


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    notif.read = True
    db.commit()
    return {"message": "Notification marked as read."}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"message": "All notifications marked as read."}


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket endpoint for real-time notification push.
    Connect with: ws://host/ws/notifications?token=<JWT>

    The token has to travel in the query string: a browser cannot set an
    Authorization header on a WebSocket handshake. It is therefore checked to
    exactly the same standard as a bearer token on a REST route — signature,
    token type, and that the user still exists — because everything pushed over
    this socket is addressed to that user.
    """
    payload = decode_jwt_token(token)
    if not payload or not payload.get("sub") or payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    # A deleted account's token stays cryptographically valid until it expires.
    # Without this the socket would still be registered under its id and receive
    # anything later addressed to it.
    if db.query(User).filter(User.id == user_id).first() is None:
        await websocket.close(code=4001, reason="Invalid or missing token")
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            # Echo back pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
