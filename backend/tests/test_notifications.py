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


# ---------------------------------------------------------------------------
# Requirement 1.5 / 7 — the rest of the notification surface
# ---------------------------------------------------------------------------


def _notification_for(db_session, user_id, message="Something happened."):
    from app.models import Notification

    notif = Notification(user_id=user_id, event_id=None, message=message, read=False)
    db_session.add(notif)
    db_session.commit()
    db_session.refresh(notif)
    return notif


def test_unread_only_filter(client, auth_headers_user_a, db_session):
    read_already = _notification_for(db_session, 1, "Old news")
    read_already.read = True
    _notification_for(db_session, 1, "Fresh news")
    db_session.commit()

    everything = client.get("/notifications", headers=auth_headers_user_a).json()
    unread = client.get("/notifications?unread_only=true", headers=auth_headers_user_a).json()

    assert len(everything) == 2
    assert [n["message"] for n in unread] == ["Fresh news"]


def test_mark_all_notifications_read(client, auth_headers_user_a, db_session):
    from app.models import Notification

    _notification_for(db_session, 1, "One")
    _notification_for(db_session, 1, "Two")

    res = client.patch("/notifications/read-all", headers=auth_headers_user_a)
    assert res.status_code == 200

    db_session.expire_all()
    assert db_session.query(Notification).filter(Notification.read == False).count() == 0  # noqa: E712


def test_mark_all_read_leaves_other_users_alone(client, auth_headers_user_a, db_session):
    from app.models import Notification

    _notification_for(db_session, 1, "Mine")
    theirs = _notification_for(db_session, 2, "Theirs")

    client.patch("/notifications/read-all", headers=auth_headers_user_a)

    db_session.expire_all()
    assert db_session.query(Notification).filter(Notification.id == theirs.id).first().read is False


def test_cannot_read_another_users_notification_list(client, auth_headers_user_b, db_session):
    _notification_for(db_session, 1, "A's private reminder")

    res = client.get("/notifications", headers=auth_headers_user_b)
    assert res.status_code == 200
    assert res.json() == []
    assert "private reminder" not in res.text


def test_cannot_mark_another_users_notification_read(client, auth_headers_user_b, db_session):
    from app.models import Notification

    theirs = _notification_for(db_session, 1, "A's reminder")

    res = client.patch(f"/notifications/{theirs.id}/read", headers=auth_headers_user_b)
    assert res.status_code == 404

    db_session.expire_all()
    assert db_session.query(Notification).filter(Notification.id == theirs.id).first().read is False


def test_notifications_require_authentication(client):
    assert client.get("/notifications").status_code == 401
