import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.notification import Notification
from app.models.shared_calendar import SharedCalendarMember

logger = logging.getLogger("notification_scheduler")
logger.setLevel(logging.INFO)

_scheduler = None


def check_upcoming_events(db: Optional[Session] = None) -> int:
    """
    Check for events starting in the next 30 minutes.
    Create one Notification per user per event, avoiding duplicates.
    Returns the number of new notifications created.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    created_count = 0
    try:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=30)

        upcoming_events = (
            db.query(Event)
            .filter(
                Event.start_time >= now,
                Event.start_time <= window_end,
            )
            .all()
        )

        logger.info(f"[SCHEDULER] Found {len(upcoming_events)} upcoming events in the next 30 min.")

        for event in upcoming_events:
            user_ids_to_notify = set()

            # Personal event owner
            if event.user_id:
                user_ids_to_notify.add(event.user_id)

            # Shared calendar members
            if event.shared_calendar_id:
                members = (
                    db.query(SharedCalendarMember)
                    .filter(SharedCalendarMember.calendar_id == event.shared_calendar_id)
                    .all()
                )
                for m in members:
                    user_ids_to_notify.add(m.user_id)

            for uid in user_ids_to_notify:
                # Dedup check: don't create if notification already exists for this user+event
                existing = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == uid,
                        Notification.event_id == event.id,
                    )
                    .first()
                )
                if existing:
                    continue

                minutes_until = int((event.start_time.replace(tzinfo=timezone.utc) - now).total_seconds() / 60)
                message = f"Reminder: '{event.title}' starts in {minutes_until} minutes."

                notif = Notification(
                    user_id=uid,
                    event_id=event.id,
                    message=message,
                    read=False,
                )
                db.add(notif)
                created_count += 1

                # Push via WebSocket (best-effort, non-blocking)
                try:
                    from app.services.ws_manager import manager
                    manager.send_to_user_sync(uid, {
                        "type": "notification",
                        "id": -1,  # Will be assigned after commit
                        "message": message,
                        "event_id": event.id,
                        "event_title": event.title,
                        "read": False,
                    })
                except Exception:
                    pass

        db.commit()
        logger.info(f"[SCHEDULER] Created {created_count} new notifications.")
    except Exception as e:
        logger.error(f"[SCHEDULER] Error checking upcoming events: {e}")
        db.rollback()
    finally:
        if own_session:
            db.close()

    return created_count


def start_scheduler():
    """Start the APScheduler background job."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            check_upcoming_events,
            "interval",
            seconds=60,
            id="check_upcoming_events",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("[SCHEDULER] APScheduler started (interval=60s).")
    except Exception as e:
        logger.warning(f"[SCHEDULER] Failed to start APScheduler: {e}")


def stop_scheduler():
    """Shut down the APScheduler gracefully."""
    global _scheduler
    if _scheduler:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
        logger.info("[SCHEDULER] APScheduler stopped.")
