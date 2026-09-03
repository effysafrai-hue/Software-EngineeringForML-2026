from datetime import datetime, timezone
import pytest
from app.models import Event, ChatMessage, Course, CourseReview
from app.db.seed_courses import seed_courses_data
from app.services.ai_agent import process_chat

MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def seed_courses_for_chat_tests(db_session):
    seed_courses_data(db_session)


def test_intent_task_and_reminder_creation(client, auth_headers_user_a, db_session):
    prompt = "Make sure I buy groceries on Thursday"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) >= 1
    ev = events[-1]
    assert "groceries" in ev.title.lower() or "buy" in ev.title.lower()
    assert ev.start_time.day == 11  # Thursday June 11, 2026


def test_intent_scheduled_appointment(client, auth_headers_user_a, db_session):
    prompt = "I have a Dr. Smith consultation at 3pm on Friday for 45 minutes"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) >= 1
    ev = events[-1]
    assert "smith" in ev.title.lower() or "consultation" in ev.title.lower()
    assert ev.start_time.day == 12  # Friday June 12
    assert ev.start_time.hour == 15
    duration_minutes = (ev.end_time - ev.start_time).total_seconds() / 60
    assert 40 <= duration_minutes <= 50


def test_intent_modify_existing_event(client, auth_headers_user_a, db_session):
    user_id = 1
    initial_event = Event(
        user_id=user_id,
        title="Dr. Smith consultation",
        description="Checkup",
        start_time=datetime(2026, 6, 12, 15, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 12, 15, 45, 0, tzinfo=timezone.utc),
    )
    db_session.add(initial_event)
    db_session.commit()

    prompt = "Please reschedule the Dr. Smith consultation to Monday at 11am"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] in ("update_event", "create_event")

    db_session.refresh(initial_event)
    assert initial_event.start_time.day == 15  # Monday June 15
    assert initial_event.start_time.hour == 11


def test_intent_cancel_event(client, auth_headers_user_a, db_session):
    user_id = 1
    initial_event = Event(
        user_id=user_id,
        title="CS50 project deadline",
        description="Milestone",
        start_time=datetime(2026, 6, 14, 23, 59, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(initial_event)
    db_session.commit()

    prompt = "Drop the CS50 project deadline from my calendar"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "delete_event"

    remaining = db_session.query(Event).filter(Event.id == initial_event.id).first()
    assert remaining is None


def test_intent_query_calendar_agenda(client, auth_headers_user_a, db_session):
    user_id = 1
    ev_tomorrow = Event(
        user_id=user_id,
        title="Sprint Planning Meeting",
        description="Review goals",
        start_time=datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev_tomorrow)
    db_session.commit()

    prompt = "what's on my plate for tomorrow"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert "sprint planning" in res["reply"].lower()


def test_intent_query_today_agenda(client, auth_headers_user_a, db_session):
    """Requirement 1.3 — 'What do I need to do today?' summarises today only."""
    user_id = 1
    db_session.add_all([
        Event(
            user_id=user_id,
            title="Statistics lecture",
            description="Hall B",
            start_time=datetime(2026, 6, 10, 14, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 10, 16, 0, 0, tzinfo=timezone.utc),
        ),
        Event(
            user_id=user_id,
            title="Dentist appointment",
            description="Far away in the future",
            start_time=datetime(2026, 6, 20, 9, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
        ),
    ])
    db_session.commit()

    res = process_chat("What do I need to do today?", user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"

    reply_lower = res["reply"].lower()
    assert "statistics" in reply_lower
    # The 20th is not today; summarising it would be a wrong answer, not a fuller one.
    assert "dentist" not in reply_lower


def test_intent_query_this_week_agenda(client, auth_headers_user_a, db_session):
    """Requirement 1.3 — 'What do I need to do this week?' summarises the week."""
    user_id = 1
    db_session.add_all([
        Event(
            user_id=user_id,
            title="Group project sync",
            description="Zoom",
            start_time=datetime(2026, 6, 11, 11, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc),
        ),
        Event(
            user_id=user_id,
            title="Physics lab report",
            description="Submit online",
            start_time=datetime(2026, 6, 13, 17, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 13, 18, 0, 0, tzinfo=timezone.utc),
        ),
    ])
    db_session.commit()

    res = process_chat("What do I need to do this week?", user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"

    reply_lower = res["reply"].lower()
    assert "group project" in reply_lower or "sync" in reply_lower
    assert "physics" in reply_lower or "lab report" in reply_lower


def test_agenda_query_only_sees_your_own_events(client, auth_headers_user_a, db_session):
    """A summary must never pull in another user's calendar."""
    db_session.add_all([
        Event(
            user_id=1,
            title="My own seminar",
            start_time=datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 11, 11, 0, 0, tzinfo=timezone.utc),
        ),
        Event(
            user_id=2,
            title="Somebody elses therapy session",
            start_time=datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 11, 13, 0, 0, tzinfo=timezone.utc),
        ),
    ])
    db_session.commit()

    res = process_chat("What is on my calendar tomorrow?", user_id=1, db=db_session, reference_time=MOCK_NOW)
    reply_lower = res["reply"].lower()

    assert "seminar" in reply_lower
    assert "therapy" not in reply_lower


def test_disambiguation_course_inquiry_not_scheduling(client, auth_headers_user_a, db_session):
    prompt = "I'm taking CS101 this semester, what are the main topics we will learn?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0

    reply_lower = res["reply"].lower()
    assert "python" in reply_lower
    assert any(topic in reply_lower for topic in ["recursion", "control flow", "functions", "object-oriented", "data structures"])


def test_mid_sentence_self_correction_scheduling(client, auth_headers_user_a, db_session):
    prompt = "Set a reminder to study CS145 on Friday... wait no, make it CS224N on Saturday at 4pm instead"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) == 1
    ev = events[0]
    assert "cs224n" in ev.title.lower()
    assert ev.start_time.day == 13  # Saturday June 13, 2026
    assert ev.start_time.hour == 16


def test_intent_9_ambiguity_clarification(client, auth_headers_user_a, db_session):
    """Ambiguous Request ('reschedule it') -> Clarification question, no blind execution."""
    prompt = "Actually can you reschedule it to next week?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None


def test_confuse_7_conditional_course_assignment_deadline(client, auth_headers_user_a, db_session):
    """Conditional course assignment deadline: creates event on Wednesday, June 17, 2026 at 5pm."""
    prompt = "If the professor doesn't give an extension, the CS224N final project is due on Wednesday at 5pm"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) == 1
    ev = events[0]
    assert "[due]" in ev.title.lower() or "cs224n" in ev.title.lower()
    assert ev.start_time.day == 17  # Wednesday June 17, 2026


def test_confuse_8_unanchored_course_pronoun_ambiguity(client, auth_headers_user_a, db_session):
    """Ambiguous unanchored pronoun question: asks for clarification with action_taken=None."""
    prompt = "How difficult is that class and can you move it to 3pm?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
