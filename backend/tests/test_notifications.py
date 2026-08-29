from datetime import datetime, timezone, timedelta
import pytest
from app.models import Event, Notification
from app.services.notification_scheduler import check_upcoming_events


def test_notification_created_for_upcoming_event(client, auth_headers_user_a, db_session):
    """Create an event starting 15 minutes from now and call the scheduler job directly.
    Verify a Notification row is created for the user."""
    user_id = 1
    start = datetime.now(timezone.utc) + timedelta(minutes=15)
    end = start + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title="Urgent Stand-up Meeting",
        description="Daily sync",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # Call the scheduler job directly (no real timer)
    created = check_upcoming_events(db=db_session)
    assert created >= 1

    # Verify notification exists in DB
    notif = (
        db_session.query(Notification)
        .filter(Notification.user_id == user_id, Notification.event_id == event.id)
        .first()
    )
    assert notif is not None
    assert notif.read is False
    assert "Urgent Stand-up Meeting" in notif.message


def test_no_duplicate_notifications(client, auth_headers_user_a, db_session):
    """Calling the scheduler job twice should not create duplicate notifications."""
    user_id = 1
    start = datetime.now(timezone.utc) + timedelta(minutes=10)
    end = start + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title="Budget Review",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()

    # Run scheduler twice
    check_upcoming_events(db=db_session)
    check_upcoming_events(db=db_session)

    # Only 1 notification should exist
    count = (
        db_session.query(Notification)
        .filter(Notification.user_id == user_id, Notification.event_id == event.id)
        .count()
    )
    assert count == 1


def test_mark_notification_read_endpoint(client, auth_headers_user_a, db_session):
    """Test the PATCH /notifications/{id}/read endpoint."""
    user_id = 1
    start = datetime.now(timezone.utc) + timedelta(minutes=20)
    end = start + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title="Architecture Review",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()

    check_upcoming_events(db=db_session)

    notif = (
        db_session.query(Notification)
        .filter(Notification.user_id == user_id, Notification.event_id == event.id)
        .first()
    )
    assert notif is not None
    assert notif.read is False

    # Mark as read
    res = client.patch(f"/notifications/{notif.id}/read", headers=auth_headers_user_a)
    assert res.status_code == 200

    db_session.refresh(notif)
    assert notif.read is True


def test_list_notifications_endpoint(client, auth_headers_user_a, db_session):
    """Test the GET /notifications endpoint returns created notifications."""
    user_id = 1
    start = datetime.now(timezone.utc) + timedelta(minutes=5)
    end = start + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title="Sprint Retro",
        start_time=start,
        end_time=end,
    )
    db_session.add(event)
    db_session.commit()

    check_upcoming_events(db=db_session)

    res = client.get("/notifications", headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert any("Sprint Retro" in n["message"] for n in data)
