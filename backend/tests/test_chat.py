from datetime import datetime, timezone, timedelta
from app.models import User, Event, ChatMessage
from app.services.ai_agent import process_chat

# Fixed reference time for all tests: Wednesday, June 10, 2026 at 10:00:00 UTC
MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)


def test_intent_1_task_reminder(client, auth_headers_user_a, db_session):
    """Category 1: Task / Reminder with novel phrasing."""
    prompt = "Make sure I buy groceries on Thursday"
    user_a_id = 1

    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"
    assert "Buy groceries" in res["reply"] or "reminder" in res["reply"].lower()

    events = db_session.query(Event).filter(Event.user_id == user_a_id).all()
    assert len(events) == 1
    event = events[0]
    assert "buy groceries" in event.title.lower()
    assert event.start_time.date() == datetime(2026, 6, 11).date()


def test_intent_2_scheduled_appointment(client, auth_headers_user_a, db_session):
    """Category 2: Scheduled Event / Appointment with exact duration."""
    prompt = "Dr. Smith consultation at 3pm on Friday for 45 minutes"
    user_a_id = 1

    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    event = db_session.query(Event).filter(Event.title.ilike("%Dr. Smith%")).first()
    assert event is not None
    assert event.start_time.date() == datetime(2026, 6, 12).date()
    assert event.start_time.hour == 15
    duration_minutes = (event.end_time - event.start_time).total_seconds() / 60
    assert duration_minutes == 45


def test_intent_3_implied_deadline(client, auth_headers_user_a, db_session):
    """Category 3: Implied Deadline marker (not phrased as a reminder)."""
    prompt = "CS50 final project submission deadline is this Sunday at 23:59"
    user_a_id = 1

    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    deadline_event = db_session.query(Event).filter(Event.title.ilike("%CS50%")).first()
    assert deadline_event is not None
    assert "[Due]" in deadline_event.title
    assert deadline_event.start_time.date() == datetime(2026, 6, 14).date()
    assert deadline_event.start_time.hour == 23
    assert deadline_event.start_time.minute == 59


def test_intent_4_modify_event(client, auth_headers_user_a, db_session):
    """Category 4: Modify / Reschedule existing event."""
    user_a_id = 1
    friday_start = datetime(2026, 6, 12, 15, 0, 0, tzinfo=timezone.utc)
    ev = Event(
        user_id=user_a_id,
        title="Dr. Smith consultation",
        start_time=friday_start,
        end_time=friday_start + timedelta(minutes=45),
    )
    db_session.add(ev)
    db_session.commit()

    prompt = "Reschedule the Dr. Smith consultation to Monday at 11am"
    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "update_event"

    updated = db_session.query(Event).filter(Event.id == ev.id).first()
    assert updated.start_time.date() == datetime(2026, 6, 15).date()
    assert updated.start_time.hour == 11


def test_intent_5_cancel_event(client, auth_headers_user_a, db_session):
    """Category 5: Cancel / Delete existing event."""
    user_a_id = 1
    ev = Event(
        user_id=user_a_id,
        title="[Due] CS50 final project",
        start_time=datetime(2026, 6, 14, 23, 59, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev)
    db_session.commit()

    prompt = "Drop the CS50 project deadline, professor gave an extension"
    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "delete_event"

    remaining = db_session.query(Event).filter(Event.id == ev.id).first()
    assert remaining is None


def test_intent_6_day_query(client, auth_headers_user_a, db_session):
    """Category 6: Query schedule for a specific day."""
    user_a_id = 1
    thursday_start = datetime(2026, 6, 11, 14, 0, 0, tzinfo=timezone.utc)
    ev = Event(
        user_id=user_a_id,
        title="Client Demo",
        start_time=thursday_start,
        end_time=thursday_start + timedelta(hours=1),
    )
    db_session.add(ev)
    db_session.commit()

    prompt = "What's on my plate for tomorrow?"
    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert "Client Demo" in res["reply"]


def test_intent_7_range_query_weekend(client, auth_headers_user_a, db_session):
    """Category 6 (Range sub-case): Query upcoming weekend agenda."""
    user_a_id = 1
    sat_event = Event(
        user_id=user_a_id,
        title="Hiking Trip",
        start_time=datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 13, 16, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(sat_event)
    db_session.commit()

    prompt = "Give me a rundown of everything happening over the upcoming weekend"
    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert "Hiking Trip" in res["reply"]


def test_intent_8_specific_event_query(client, auth_headers_user_a, db_session):
    """Category 6 (Lookup sub-case): Find specific appointment time."""
    user_a_id = 1
    ev = Event(
        user_id=user_a_id,
        title="Dr. Smith Consultation",
        start_time=datetime(2026, 6, 12, 15, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 12, 15, 45, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev)
    db_session.commit()

    prompt = "At what time is my Dr. Smith appointment?"
    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert "Dr. Smith" in res["reply"]
    assert "3:00 PM" in res["reply"] or "15:00" in res["reply"] or "June 12" in res["reply"]


def test_intent_9_ambiguous_request_triggers_clarification(client, auth_headers_user_a, db_session):
    """Category Ambiguity: Unspecified event triggers targeted clarification, 0 mutations."""
    user_a_id = 1
    prompt = "Can you move that thing to later?"

    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert "?" in res["reply"]
    assert "which" in res["reply"].lower() or "event" in res["reply"].lower()

    assert db_session.query(Event).count() == 0


def test_intent_10_general_conversation_zero_tool_calls(client, auth_headers_user_a, db_session):
    """Category 7: Chit-chat produces conversational answer with zero tool calls."""
    user_a_id = 1
    prompt = "How are you doing today? What can you do for me?"

    res = process_chat(prompt, user_id=user_a_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert "calendar" in res["reply"].lower() or "schedule" in res["reply"].lower() or "hello" in res["reply"].lower()
    assert db_session.query(Event).count() == 0


def test_chat_endpoint_persists_messages(client, auth_headers_user_a, db_session):
    """Verify POST /chat endpoint persists both user and assistant messages in chat_messages."""
    prompt = "Make sure I buy groceries on Thursday"
    response = client.post(
        "/chat",
        json={"message": prompt},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data

    messages = db_session.query(ChatMessage).all()
    assert len(messages) >= 2
    assert messages[0].role == "user"
    assert messages[0].content == prompt
    assert messages[1].role == "assistant"
