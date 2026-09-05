"""Long-term memory as judged by a real model — requirement 2.4 and 2.5.

`tests/test_user_memory.py` covers everything around the model deterministically:
storage, expiry, eviction, the API, and the fact that the memory block is built
into every prompt. What it cannot cover is the judgement itself — whether the
model chooses to keep "I always want the hardest task first", leaves "remind me
to buy milk" alone, and lets a stored constraint change what it advises today.

That is what these tests check, so they send real requests and are marked
`live_llm`: `pytest --no-ai` excludes them, and a failure here can mean the model
had an off day rather than that the code broke. Assertions are deliberately
loose — they check that a fact of the right shape was stored or used, not that
the model phrased it a particular way.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Event, UserMemory
from app.services import user_memory
from app.services.ai_agent import process_chat

MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)

# Times here are read as the raw stored instant, which is only meaningful because
# the suite pins the default zone to UTC (`pinned_default_timezone` in
# conftest.py). Wall-clock conversion is tests/test_timezones.py' subject, not
# this file's.
pytestmark = pytest.mark.live_llm

USER_ID = 1


def _live_memories(db):
    return user_memory.active_memories(db, USER_ID)


def _memory_text(db):
    return " ".join(m.content.lower() for m in _live_memories(db))


def test_a_stated_preference_is_remembered(db_session):
    """Requirement 2.4 — the model decides this is worth keeping, unprompted."""
    process_chat(
        "Just so you know, I always want to do the hardest task first while I'm fresh.",
        user_id=USER_ID,
        db=db_session,
        reference_time=MOCK_NOW,
    )

    stored = _live_memories(db_session)
    assert stored, "the model stored nothing about a plainly durable preference"
    assert "hard" in _memory_text(db_session)
    assert all(m.source == "ai" for m in stored)


def test_a_temporary_state_is_remembered_with_a_horizon(db_session):
    """The example from the guidelines: being unwell this week is not permanent."""
    process_chat(
        "I feel really unwell and I won't be able to do much this week.",
        user_id=USER_ID,
        db=db_session,
        reference_time=MOCK_NOW,
    )

    stored = _live_memories(db_session)
    assert stored, "the model stored nothing about being unable to work this week"
    text = _memory_text(db_session)
    assert any(word in text for word in ("unwell", "ill", "sick", "unable", "little", "light"))

    # A horizon is what stops it applying for ever. Not every run sets one, so
    # this only checks that anything it does set is a matter of days, not years.
    for mem in stored:
        if mem.expires_at is not None:
            horizon = user_memory._as_utc(mem.expires_at) - MOCK_NOW
            assert timedelta(days=1) <= horizon <= timedelta(days=31)


def test_a_stored_constraint_changes_what_the_ai_suggests_today(db_session):
    """Requirement 2.5, the guidelines' own example — the memory has to reach the
    advice, not just the database."""
    user_memory.remember(
        db_session,
        USER_ID,
        "is unwell this week and can only manage light, short tasks",
        category="constraint",
        expires_in_days=7,
        now=MOCK_NOW,
    )
    for hour, title in ((9, "Rewrite the whole ML report"), (14, "Gym session"), (17, "Read one paper")):
        start = MOCK_NOW.replace(hour=hour)
        db_session.add(
            Event(user_id=USER_ID, title=title, start_time=start, end_time=start + timedelta(hours=2))
        )
    db_session.commit()

    res = process_chat(
        "What should I do today?", user_id=USER_ID, db=db_session, reference_time=MOCK_NOW
    )

    reply = res["reply"].lower()
    assert any(
        word in reply
        for word in ("unwell", "ill", "rest", "light", "gentle", "easy", "recover", "not feeling", "take it easy")
    ), f"the reply ignored the stored constraint: {res['reply']}"


def test_a_retracted_fact_is_discarded(db_session):
    """Requirement 2.4 — the model has to be able to drop what it knows, too."""
    stale = user_memory.remember(
        db_session, USER_ID, "is unwell this week and can only manage light work", category="constraint"
    )

    process_chat(
        "I'm completely better now - forget that I was ill, I'm back to full speed.",
        user_id=USER_ID,
        db=db_session,
        reference_time=MOCK_NOW,
    )

    refreshed = db_session.query(UserMemory).filter(UserMemory.id == stale.id).first()
    assert refreshed.active is False, "the assistant is still carrying a constraint the user retracted"


def test_a_one_off_request_is_scheduled_rather_than_remembered(db_session):
    """The other half of deciding what to keep: an errand is an event, not a
    lasting fact about the user. Remembering it would fill the prompt with noise."""
    res = process_chat(
        "Remind me to buy milk tomorrow at 5pm", user_id=USER_ID, db=db_session, reference_time=MOCK_NOW
    )

    assert res["action_taken"] == "create_event"
    assert db_session.query(Event).filter(Event.user_id == USER_ID).count() == 1
    assert "milk" not in _memory_text(db_session)


def test_a_remembered_constraint_does_not_block_a_requested_action(db_session):
    """A preference shapes how the assistant schedules, never whether it does."""
    user_memory.remember(
        db_session, USER_ID, "is unwell this week and can only manage light work", category="constraint"
    )

    res = process_chat(
        "Book my dentist appointment for Thursday at 3pm",
        user_id=USER_ID,
        db=db_session,
        reference_time=MOCK_NOW,
    )

    assert res["action_taken"] == "create_event"
    event = db_session.query(Event).filter(Event.user_id == USER_ID).one()
    assert event.start_time.day == 11 and event.start_time.hour == 15


def test_the_signup_profile_is_used_from_the_first_message(client, db_session):
    """Requirement 2.2 — asking at sign-up only pays off if the AI reads the answers."""
    user_memory.seed_from_signup_answers(
        db_session,
        USER_ID,
        {"communication_style": "brief", "task_order": "hard_first", "interests": ["linear algebra"]},
    )

    res = process_chat(
        "I have three things to get through today - where do I start?",
        user_id=USER_ID,
        db=db_session,
        reference_time=MOCK_NOW,
    )

    # The profile says "hardest first", so that is the shape the answer should take.
    assert any(word in res["reply"].lower() for word in ("hard", "toughest", "difficult", "demanding"))
