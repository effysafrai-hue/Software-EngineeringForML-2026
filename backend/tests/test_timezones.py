"""Wall-clock correctness in the AI path.

The reported bug: the assistant replies "I've set the meeting for 6pm" and the
calendar shows 9pm. The chat path treated the hour the user said as UTC, while
the browser renders the stored instant in the reader's zone — so every time was
off by the user's offset (three hours, for Asia/Jerusalem in summer).

Three things have to hold, and there is a section below for each:

* a wall clock the user states is stored as the instant that renders back to the
  same wall clock (18:00 local -> 15:00Z -> 18:00 local);
* "today", "tomorrow" and the weekday table are the user's local dates, not
  UTC's, so a request made late in the evening does not land on the next day; and
* what the tools hand back to the model is local too, so the hour the assistant
  says is the hour on the calendar.

The manual (non-AI) calendar path was already correct — the browser converts
local -> UTC before sending — and is covered here as a regression guard.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import Event, User
from app.services import timezones
from app.services.ai_agent import (
    create_event_tool,
    list_events_tool,
    parse_iso_datetime,
    process_chat,
    update_event_tool,
)
from app.services.llm_client import LLMResponse

# Asia/Jerusalem is UTC+3 in June (IDT), which is exactly the offset behind the
# reported symptom.
JERUSALEM = "Asia/Jerusalem"
JERUSALEM_TZ = ZoneInfo(JERUSALEM)
OFFSET_HOURS = 3

# Wednesday 2026-06-10, 10:00 UTC = 13:00 local.
MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)


class FakeLLM:
    """Scripted model: records the prompt, optionally makes tool calls."""

    def __init__(self):
        self.system_instructions = []
        self.reply = "Done."
        self.script = []
        self.tool_results = []

    def generate(self, system_instruction, user_message, tools, tool_schemas=None, tool_executors=None):
        self.system_instructions.append(system_instruction)
        if self.script:
            self.tool_results.append(self.script.pop(0)(tool_executors or {}))
        return LLMResponse(reply=self.reply, executed_actions=[])

    @property
    def last_prompt(self):
        return self.system_instructions[-1]


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr("app.services.ai_agent.settings.LLM_PROVIDER", "ollama")
    monkeypatch.setattr("app.services.llm_client.get_llm_client", lambda: fake)
    return fake


def _stored_utc(value: datetime) -> datetime:
    """Normalise a timestamp read back from the database.

    SQLite has no zone-aware type, so a `DateTime(timezone=True)` column written
    as UTC reads back *naive* under the test engine while Postgres returns it
    aware. Calling `.astimezone()` on the naive value would silently re-read it
    as the machine's own zone — the same class of mistake these tests exist to
    catch — so every assertion goes through here.
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _stored_local(value: datetime, tz=JERUSALEM_TZ) -> datetime:
    """The same instant as the user's browser would render it."""
    return _stored_utc(value).astimezone(tz)


# ---------------------------------------------------------------------------
# The reported bug
# ---------------------------------------------------------------------------


def test_a_6pm_request_is_stored_as_6pm_local(db_session):
    """The bug, in one assertion.

    The model writes the wall clock it was told ("18:00"); the row has to be the
    instant that renders as 18:00 in the user's zone, i.e. 15:00Z at UTC+3.
    Storing 18:00Z is what made the calendar show 9pm.
    """
    result = create_event_tool(
        1, db_session, "Team meeting", "2026-06-11T18:00:00+03:00", "", tz=JERUSALEM_TZ
    )
    assert result["status"] == "success"

    stored = db_session.query(Event).one()
    assert _stored_utc(stored.start_time).hour == 18 - OFFSET_HOURS

    # And it renders back as the hour the user asked for.
    assert _stored_local(stored.start_time).hour == 18


def test_what_the_model_is_told_matches_what_the_calendar_will_show(db_session):
    """The reply quotes the tool result, so the tool result has to be local.

    Handing back "18:00Z" is what let the assistant announce 6pm for an event the
    calendar displayed at 9pm.
    """
    result = create_event_tool(
        1, db_session, "Team meeting", "2026-06-11T18:00:00+03:00", "", tz=JERUSALEM_TZ
    )

    assert result["event"]["start_time"].startswith("2026-06-11T18:00:00")
    assert "+03:00" in result["event"]["start_time"]
    assert "18:00:00" in result["message"]


def test_a_naive_timestamp_is_read_as_the_users_wall_clock(db_session):
    """The likeliest thing a model writes when told "no timezone"."""
    create_event_tool(1, db_session, "Gym", "2026-06-11T18:00:00", "", tz=JERUSALEM_TZ)

    stored = db_session.query(Event).one()
    assert _stored_local(stored.start_time).hour == 18


def test_a_stray_z_is_read_as_the_users_wall_clock_too(db_session):
    """The prompt forbids "Z", but models are trained on UTC-shaped ISO strings
    and append it out of habit to the local time they were told to write.

    Reading it as UTC is the failure being fixed: the assistant's own reply
    quotes 18:00, so the event has to be 18:00 local. Documented in
    `parse_iso_datetime`.
    """
    create_event_tool(1, db_session, "Dinner", "2026-06-11T18:00:00Z", "", tz=JERUSALEM_TZ)

    stored = db_session.query(Event).one()
    assert _stored_local(stored.start_time).hour == 18


def test_a_utc_user_is_unaffected(db_session):
    """The default zone must keep behaving exactly as before."""
    create_event_tool(1, db_session, "Standup", "2026-06-11T09:00:00Z", "")

    stored = db_session.query(Event).one()
    assert _stored_utc(stored.start_time).hour == 9


def test_rescheduling_also_lands_on_the_stated_hour(db_session):
    start = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    event = Event(user_id=1, title="Dentist", start_time=start, end_time=start + timedelta(hours=1))
    db_session.add(event)
    db_session.commit()

    result = update_event_tool(
        1, db_session, event.id, start_time="2026-06-12T20:00:00+03:00", tz=JERUSALEM_TZ
    )

    assert result["status"] == "success"
    db_session.refresh(event)
    assert _stored_local(event.start_time).hour == 20
    # Duration is preserved when only the start moves.
    assert event.end_time - event.start_time == timedelta(hours=1)
    assert result["event"]["start_time"].startswith("2026-06-12T20:00:00")


def test_a_listed_event_is_reported_in_local_time(db_session):
    """Agenda summaries had the same bug in reverse: the model read 15:00Z off
    an event the user sees at 18:00 and told them "3pm"."""
    start = datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc)  # 18:00 local
    db_session.add(Event(user_id=1, title="Seminar", start_time=start, end_time=start + timedelta(hours=1)))
    db_session.commit()

    result = list_events_tool(1, db_session, tz=JERUSALEM_TZ)

    assert result["events"][0]["start_time"].startswith("2026-06-11T18:00:00")


def test_a_local_range_filter_selects_the_local_day(db_session):
    """23:00 local on the 11th is 20:00Z on the 11th; 00:30 local on the 12th is
    21:30Z on the 11th. Filtering by the local day has to catch both."""
    late = datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc)      # 23:00 local, 11th
    after_midnight = datetime(2026, 6, 11, 21, 30, tzinfo=timezone.utc)  # 00:30 local, 12th
    db_session.add_all([
        Event(user_id=1, title="Late study", start_time=late, end_time=late + timedelta(hours=1)),
        Event(user_id=1, title="Night owl", start_time=after_midnight, end_time=after_midnight + timedelta(hours=1)),
    ])
    db_session.commit()

    eleventh = list_events_tool(
        1, db_session, "2026-06-11T00:00:00", "2026-06-11T23:59:59", tz=JERUSALEM_TZ
    )
    titles = [e["title"] for e in eleventh["events"]]

    assert "Late study" in titles
    assert "Night owl" not in titles


# ---------------------------------------------------------------------------
# What the model is told
# ---------------------------------------------------------------------------


def test_the_prompt_states_the_local_time_zone_and_offset(db_session, fake_llm):
    process_chat(
        "Book a meeting", user_id=1, db=db_session, reference_time=MOCK_NOW, timezone_name=JERUSALEM
    )

    prompt = fake_llm.last_prompt
    assert JERUSALEM in prompt
    assert "+03:00" in prompt
    # 10:00 UTC is 13:00 local — the model must be given the local clock.
    assert "2026-06-10T13:00:00+03:00" in prompt


def test_the_prompt_forbids_converting_to_utc(db_session, fake_llm):
    """The instruction that stops the model doing the offset arithmetic itself."""
    process_chat(
        "Book a meeting", user_id=1, db=db_session, reference_time=MOCK_NOW, timezone_name=JERUSALEM
    )

    prompt = fake_llm.last_prompt
    assert "NEVER convert a time to UTC" in prompt
    assert '"6pm" -> "18:00:00"' in prompt
    # The example timestamp carries the user's offset, not Z.
    assert "T09:00:00+03:00" in prompt


def test_today_and_tomorrow_follow_the_local_date(db_session, fake_llm):
    """00:30 local on Thursday is still Wednesday in UTC.

    Anchoring the prompt to UTC put "today" a day behind for anyone east of it
    late in the evening, so a "tonight" request landed on the wrong date.
    """
    late_evening_utc = datetime(2026, 6, 10, 21, 30, tzinfo=timezone.utc)  # 00:30 local, 11th

    process_chat(
        "What is on today?",
        user_id=1,
        db=db_session,
        reference_time=late_evening_utc,
        timezone_name=JERUSALEM,
    )

    prompt = fake_llm.last_prompt
    assert "Today is Thursday, 2026-06-11" in prompt
    assert "- Friday = 2026-06-12  <- tomorrow" in prompt


def test_a_utc_user_gets_the_same_prompt_as_before(db_session, fake_llm):
    """No timezone supplied: the behaviour every existing test relies on."""
    process_chat("Book a meeting", user_id=1, db=db_session, reference_time=MOCK_NOW)

    prompt = fake_llm.last_prompt
    assert "Today is Wednesday, 2026-06-10" in prompt
    assert "2026-06-10T10:00:00+00:00" in prompt


def test_the_whole_turn_round_trips_the_stated_hour(db_session, fake_llm):
    """End to end, with the model doing what the prompt asks: 6pm in, 6pm out."""
    fake_llm.script = [
        lambda ex: ex["create_event"](
            title="Team meeting",
            start_time="2026-06-11T18:00:00+03:00",
            end_time="2026-06-11T19:00:00+03:00",
        )
    ]

    result = process_chat(
        "Set up a team meeting tomorrow at 6pm",
        user_id=1,
        db=db_session,
        reference_time=MOCK_NOW,
        timezone_name=JERUSALEM,
    )

    assert result["action_taken"] == "create_event"
    event = db_session.query(Event).one()
    # What the user will see in the calendar.
    assert _stored_local(event.start_time).strftime("%Y-%m-%d %H:%M") == "2026-06-11 18:00"
    # What the model was told, and will therefore repeat in its reply.
    assert fake_llm.tool_results[0]["event"]["start_time"].startswith("2026-06-11T18:00:00")


# ---------------------------------------------------------------------------
# Resolving and remembering the zone
# ---------------------------------------------------------------------------


def test_the_browsers_zone_is_used_and_remembered(client, auth_headers_user_a, db_session, fake_llm):
    res = client.post(
        "/chat",
        json={"message": "Book something", "timezone": JERUSALEM},
        headers=auth_headers_user_a,
    )

    assert res.status_code == 200
    assert JERUSALEM in fake_llm.last_prompt
    # Persisted, so anything that runs without a request in hand has a wall clock.
    assert db_session.query(User).filter(User.id == 1).one().timezone == JERUSALEM


def test_a_later_request_without_a_zone_falls_back_to_the_remembered_one(
    client, auth_headers_user_a, db_session, fake_llm
):
    client.post("/chat", json={"message": "First", "timezone": JERUSALEM}, headers=auth_headers_user_a)
    client.post("/chat", json={"message": "Second"}, headers=auth_headers_user_a)

    assert JERUSALEM in fake_llm.system_instructions[1]


def test_an_unusable_zone_is_ignored_rather_than_stored(
    client, auth_headers_user_a, db_session, fake_llm
):
    """A broken client must not overwrite a good zone with junk, or fail the turn."""
    client.post("/chat", json={"message": "First", "timezone": JERUSALEM}, headers=auth_headers_user_a)

    res = client.post(
        "/chat",
        json={"message": "Second", "timezone": "Mars/Olympus_Mons"},
        headers=auth_headers_user_a,
    )

    assert res.status_code == 200
    assert db_session.query(User).filter(User.id == 1).one().timezone == JERUSALEM
    assert JERUSALEM in fake_llm.system_instructions[1]


def test_the_shared_calendar_chat_uses_the_same_wall_clock(
    client, auth_headers_user_a, fake_llm
):
    cal_id = client.post(
        "/shared-calendars", json={"name": "Study Group"}, headers=auth_headers_user_a
    ).json()["id"]

    res = client.post(
        f"/shared-calendars/{cal_id}/chat",
        json={"message": "When are we meeting?", "timezone": JERUSALEM},
        headers=auth_headers_user_a,
    )

    assert res.status_code == 200
    assert "+03:00" in fake_llm.last_prompt


@pytest.mark.parametrize("name", [None, "", "   ", "Not/AZone", "UTC+3", 42])
def test_an_unusable_zone_falls_back_to_the_configured_default(name, monkeypatch):
    """An unknown zone must not raise: a bad header is not a reason to refuse to
    schedule anything.

    The setting is pinned here rather than assumed, because it is exactly the
    knob a deployment is expected to change — a test that hardcodes UTC passes
    on a developer's laptop and fails on a configured server.
    """
    monkeypatch.setattr(timezones.settings, "DEFAULT_TIMEZONE", "Europe/Paris")

    assert timezones.zone_name(timezones.resolve_timezone(name)) == "Europe/Paris"


@pytest.mark.parametrize("name", [None, "", "Not/AZone"])
def test_a_broken_default_setting_still_lands_on_utc(name, monkeypatch):
    """Last resort: a misconfigured DEFAULT_TIMEZONE must not break scheduling."""
    monkeypatch.setattr(timezones.settings, "DEFAULT_TIMEZONE", "Mars/Olympus_Mons")

    assert timezones.resolve_timezone(name) is timezones.UTC


def test_resolution_prefers_the_first_usable_candidate():
    assert timezones.zone_name(timezones.resolve_timezone(None, JERUSALEM)) == JERUSALEM
    assert timezones.zone_name(timezones.resolve_timezone("Europe/Paris", JERUSALEM)) == "Europe/Paris"
    assert timezones.zone_name(timezones.resolve_timezone("Mars/Base", JERUSALEM)) == JERUSALEM


def test_the_configured_default_is_what_an_unreported_browser_gets(db_session, fake_llm, monkeypatch):
    """The `DEFAULT_TIMEZONE` path, end to end.

    A client that sends no zone must still get its own wall clock, which is why
    the setting is worth configuring rather than leaving on UTC.
    """
    monkeypatch.setattr("app.services.timezones.settings.DEFAULT_TIMEZONE", JERUSALEM)

    process_chat("Book something", user_id=1, db=db_session, reference_time=MOCK_NOW)

    assert JERUSALEM in fake_llm.last_prompt
    assert "2026-06-10T13:00:00+03:00" in fake_llm.last_prompt


def test_the_offset_label_follows_daylight_saving():
    """The label is handed to the model as a literal, so it has to be right for
    the day in question — Israel is +03:00 in June and +02:00 in January."""
    summer = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    winter = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)

    assert timezones.offset_label(JERUSALEM_TZ, summer) == "+03:00"
    assert timezones.offset_label(JERUSALEM_TZ, winter) == "+02:00"


def test_a_winter_wall_clock_uses_the_winter_offset(db_session):
    """The stored instant must come from the offset in force on that date, not
    from a hardcoded one."""
    create_event_tool(1, db_session, "Winter exam", "2026-01-15T18:00:00", "", tz=JERUSALEM_TZ)

    stored = db_session.query(Event).one()
    assert _stored_utc(stored.start_time).hour == 16  # 18:00 at UTC+2
    assert _stored_local(stored.start_time).hour == 18


def test_parse_rejects_a_relative_phrase():
    """Unchanged behaviour: a phrase like "Saturday 4pm" is handed back to the
    model rather than guessed at."""
    with pytest.raises(ValueError):
        parse_iso_datetime("Saturday 4pm", JERUSALEM_TZ)
    with pytest.raises(ValueError):
        parse_iso_datetime("", JERUSALEM_TZ)


# ---------------------------------------------------------------------------
# Regression: the manual path was already correct
# ---------------------------------------------------------------------------


@pytest.mark.live_llm
def test_a_real_model_puts_a_6pm_request_at_6pm_local(db_session):
    """The reported bug, against a real model.

    Everything above pins the code around the model. This is the only test that
    checks the thing that actually went wrong in production: what the model
    writes when a user at UTC+3 says "6pm". Marked live_llm — slow, needs a key.
    """
    res = process_chat(
        "Set up a team meeting tomorrow at 6pm",
        user_id=1,
        db=db_session,
        reference_time=MOCK_NOW,
        timezone_name=JERUSALEM,
    )

    assert res["action_taken"] == "create_event"
    event = db_session.query(Event).filter(Event.user_id == 1).one()
    local = _stored_local(event.start_time)

    assert local.hour == 18, f"the calendar will show {local:%H:%M} for a 6pm request"
    assert local.strftime("%Y-%m-%d") == "2026-06-11"

    # The reply is what the user reads, and the whole complaint was that it
    # named a different hour from the calendar.
    reply = res["reply"].lower()
    assert any(form in reply for form in ("6:00", "18:00", "6 pm", "6pm")), res["reply"]


def test_the_manual_calendar_path_stores_the_instant_it_is_given(client, auth_headers_user_a, db_session):
    """The event modal converts local -> UTC in the browser (`toISOString`), so
    the API must store exactly the instant it receives and not re-interpret it."""
    res = client.post(
        "/events",
        json={
            "title": "Manually added",
            "start_time": "2026-06-11T15:00:00Z",  # 18:00 in Jerusalem
            "end_time": "2026-06-11T16:00:00Z",
        },
        headers=auth_headers_user_a,
    )

    assert res.status_code == 201
    stored = db_session.query(Event).one()
    assert _stored_utc(stored.start_time).hour == 15
    assert _stored_local(stored.start_time).hour == 18
