from datetime import datetime, timezone
import pytest
from app.models import Event, ChatMessage, Course, CourseReview
from app.db.seed_courses import seed_courses_data
from app.services.ai_agent import process_chat

# Fixed reference time for deterministic testing: Wednesday, June 10, 2026, 10:00:00 UTC
MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def seed_courses_for_chat_tests(db_session):
    """Seed course knowledge base into in-memory test database."""
    seed_courses_data(db_session)


# ============================================================================
# PART 1: 10 BASELINE INTENT CATEGORY TESTS
# ============================================================================

def test_intent_1_task_reminder(client, auth_headers_user_a, db_session):
    """Intent 1: Task / Reminder -> create_event tool"""
    prompt = "Make sure I buy groceries on Thursday"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) >= 1
    ev = events[-1]
    assert "groceries" in ev.title.lower() or "buy" in ev.title.lower()
    assert ev.start_time.year == 2026
    assert ev.start_time.month == 6
    assert ev.start_time.day == 11  # Thursday


def test_intent_2_scheduled_appointment(client, auth_headers_user_a, db_session):
    """Intent 2: Scheduled Appointment with duration -> create_event tool"""
    prompt = "I have a Dr. Smith consultation at 3pm on Friday for 45 minutes"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) >= 1
    ev = events[-1]
    assert "smith" in ev.title.lower() or "consultation" in ev.title.lower()
    assert ev.start_time.day == 12  # Friday
    assert ev.start_time.hour == 15
    duration_minutes = (ev.end_time - ev.start_time).total_seconds() / 60
    assert 40 <= duration_minutes <= 50


def test_intent_3_implied_deadline(client, auth_headers_user_a, db_session):
    """Intent 3: Implied Deadline -> create_event tool with [Due] prefix"""
    prompt = "My CS50 final project submission deadline is this Sunday at 23:59"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) >= 1
    ev = events[-1]
    assert "due" in ev.title.lower() or "cs50" in ev.title.lower()
    assert ev.start_time.day == 14  # Sunday June 14, 2026


def test_intent_4_modify_event(client, auth_headers_user_a, db_session):
    """Intent 4: Modify Existing Event -> update_event tool"""
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


def test_intent_5_cancel_event(client, auth_headers_user_a, db_session):
    """Intent 5: Cancel / Delete Event -> delete_event tool"""
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


def test_intent_6_day_query(client, auth_headers_user_a, db_session):
    """Intent 6: Day Query ("what's on my plate for tomorrow") -> list_events tool"""
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


def test_intent_7_range_query(client, auth_headers_user_a, db_session):
    """Intent 7: Range Query ("rundown of the upcoming weekend") -> list_events tool"""
    user_id = 1
    ev_weekend = Event(
        user_id=user_id,
        title="Hiking trip",
        description="Mountain trail",
        start_time=datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev_weekend)
    db_session.commit()

    prompt = "give me a rundown of the upcoming weekend"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert "hiking" in res["reply"].lower()


def test_intent_8_conversational_no_action(client, auth_headers_user_a, db_session):
    """Intent 8: Pure Conversational / Greeting -> No action taken"""
    prompt = "Hello! How are you doing today?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert len(res["reply"]) > 5
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0


def test_intent_9_ambiguity_clarification(client, auth_headers_user_a, db_session):
    """Intent 9: Ambiguous Request ("reschedule it") -> Clarification question, no blind execution"""
    prompt = "Actually can you reschedule it to next week?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()
    assert any(w in reply_lower for w in ["which", "what", "clarify", "specify", "event"])


def test_intent_10_invalid_time_range_handling(client, auth_headers_user_a, db_session):
    """Intent 10: Event creation auto-corrects end_time if end <= start"""
    prompt = "Sync with Alex on Monday at 10am for 30 mins"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    ev = db_session.query(Event).filter(Event.user_id == user_id).first()
    assert ev is not None
    assert ev.end_time > ev.start_time
    assert ev.start_time.hour == 10
    assert ev.start_time.day == 15  # Monday


# ============================================================================
# PART 2: 10 ADVANCED CONFUSION TESTS (FEATURING COURSE KNOWLEDGE BASE)
# ============================================================================

def test_confuse_1_course_statement_not_event_creation(client, auth_headers_user_a, db_session):
    """
    Confusion 1: User makes a statement about taking a course & asks syllabus question.
    AI must NOT schedule a calendar event; it must return grounded course topics.
    """
    prompt = "I'm taking CS101 this semester, what are the main topics we will learn?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0

    reply_lower = res["reply"].lower()
    assert "python" in reply_lower
    assert any(topic in reply_lower for topic in ["recursion", "control flow", "functions", "object-oriented", "data structures"])


def test_confuse_2_past_negation_nonexistent_course(client, auth_headers_user_a, db_session):
    """
    Confusion 2: Retrospection & Past Negation referencing a nonexistent course.
    AI must acknowledge conversationally with 0 calendar events and 0 mutations.
    """
    prompt = "I decided not to register for CS999 Advanced Quantum Propulsion yesterday"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0


def test_confuse_3_mid_sentence_course_and_date_correction(client, auth_headers_user_a, db_session):
    """
    Confusion 3: Mid-sentence self-correction changing both course code and day/time.
    AI must book the corrected course (CS224N on Saturday at 4pm), not CS145 on Friday.
    """
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


def test_confuse_4_course_study_session_interrogative_scheduling(client, auth_headers_user_a, db_session):
    """
    Confusion 4: Interrogative scheduling for a course study session.
    AI must execute create_event for CS229 study session on Monday at 10am for 45 mins.
    """
    prompt = "Can we set up a 45-minute study session for CS229 on Monday at 10am?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) == 1
    ev = events[0]
    assert "cs229" in ev.title.lower() or "study" in ev.title.lower()
    assert ev.start_time.day == 15  # Monday June 15
    assert ev.start_time.hour == 10
    duration_mins = (ev.end_time - ev.start_time).total_seconds() / 60
    assert 40 <= duration_mins <= 50


def test_confuse_5_course_review_conflict_query(client, auth_headers_user_a, db_session):
    """
    Confusion 5: Conflict check mentioning a course session.
    AI must run list_events query and NOT create a new calendar event.
    """
    user_id = 1
    prompt = "Do I have anything clashing with my 3pm CS101 review session on Tuesday?"

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0


def test_confuse_6_fractional_duration_course_prep(client, auth_headers_user_a, db_session):
    """
    Confusion 6: Fractional duration math (2.5 hours) for course project prep.
    AI must create an event for 150 minutes starting at 1:30 PM tomorrow.
    """
    prompt = "Block off 2 and a half hours starting from 1:30pm tomorrow for CS224N project prep"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) == 1
    ev = events[0]
    assert "cs224n" in ev.title.lower() or "prep" in ev.title.lower()
    assert ev.start_time.day == 11  # Thursday June 11
    assert ev.start_time.hour == 13 and ev.start_time.minute == 30
    duration_minutes = (ev.end_time - ev.start_time).total_seconds() / 60
    assert 140 <= duration_minutes <= 160


def test_confuse_7_conditional_course_assignment_deadline(client, auth_headers_user_a, db_session):
    """
    Confusion 7: Conditional course assignment deadline.
    AI must create a deadline event with [Due] prefix for Wednesday at 5pm.
    """
    prompt = "If the professor doesn't give an extension, the CS224N final project is due on Wednesday at 5pm"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "create_event"

    events = db_session.query(Event).filter(Event.user_id == user_id).all()
    assert len(events) == 1
    ev = events[0]
    assert "[due]" in ev.title.lower() or "cs224n" in ev.title.lower()
    assert ev.start_time.day == 17  # Wednesday June 17, 2026
    assert ev.start_time.hour == 17


def test_confuse_8_unanchored_course_pronoun_ambiguity(client, auth_headers_user_a, db_session):
    """
    Confusion 8: Ambiguous unanchored pronoun question.
    AI must ask for clarification and not mutate the database or invent a course.
    """
    prompt = "How difficult is that class and can you move it to 3pm?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    assert db_session.query(Event).filter(Event.user_id == user_id).count() == 0
    reply_lower = res["reply"].lower()
    assert any(q in reply_lower for q in ["which", "what", "referring", "specify", "course", "event"])


def test_confuse_9_composite_course_lookup_query(client, auth_headers_user_a, db_session):
    """
    Confusion 9: Specific course event lookup + calendar agenda query.
    AI must call list_events and report the correct event time.
    """
    user_id = 1
    ev_ta = Event(
        user_id=user_id,
        title="CS101 TA Office Hours",
        description="Ask recursion homework questions",
        start_time=datetime(2026, 6, 11, 15, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 16, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev_ta)
    db_session.commit()

    prompt = "What time is my CS101 TA session on Thursday, and am I free 2 hours before it?"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "list_events"
    reply_lower = res["reply"].lower()
    assert "3" in reply_lower or "15:00" in reply_lower or "cs101" in reply_lower or "ta" in reply_lower


def test_confuse_10_polite_indirect_course_group_cancellation(client, auth_headers_user_a, db_session):
    """
    Confusion 10: Polite indirect cancellation of a course study group.
    AI must detect the cancellation intent and remove the event.
    """
    user_id = 1
    ev_study = Event(
        user_id=user_id,
        title="CS145 Database Study Group",
        description="Prepare for normalization quiz",
        start_time=datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 30, 0, tzinfo=timezone.utc),
    )
    db_session.add(ev_study)
    db_session.commit()

    prompt = "I'm feeling under the weather so I won't be able to make it to the CS145 database study group tomorrow"
    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] == "delete_event"

    remaining = db_session.query(Event).filter(Event.id == ev_study.id).first()
    assert remaining is None
