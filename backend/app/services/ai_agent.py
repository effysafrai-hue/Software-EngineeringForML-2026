import logging
import sys
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import re
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.models import User, Event, ChatMessage, Course, CourseReview
from app.services.course_grounding import retrieve_relevant_courses

logger = logging.getLogger("ai_agent")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [AI_AGENT] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

_RESOLVED_MODEL_NAME: Optional[str] = None


def resolve_best_gemini_model() -> str:
    global _RESOLVED_MODEL_NAME
    if _RESOLVED_MODEL_NAME:
        return _RESOLVED_MODEL_NAME

    if not settings.GEMINI_API_KEY or genai is None:
        return settings.GEMINI_MODEL or "gemini-1.5-flash"

    priority_candidates = [
        settings.GEMINI_MODEL,
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-pro",
    ]

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        available = []
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                clean_name = m.name.replace("models/", "")
                available.append(clean_name)

        for candidate in priority_candidates:
            if candidate and candidate in available:
                _RESOLVED_MODEL_NAME = candidate
                return _RESOLVED_MODEL_NAME

        if available:
            _RESOLVED_MODEL_NAME = available[0]
            return _RESOLVED_MODEL_NAME
    except Exception:
        pass

    _RESOLVED_MODEL_NAME = settings.GEMINI_MODEL or "gemini-1.5-flash"
    return _RESOLVED_MODEL_NAME


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an absolute ISO 8601 timestamp, assuming UTC when no offset is given.

    Only absolute timestamps are accepted. A loose parser would turn a relative
    phrase like "Saturday 4pm" into a date anchored to the real clock rather than
    the conversation's reference time, quietly storing the wrong day; the caller
    reports the rejection to the model instead, which can then send a real
    timestamp.
    """
    if not dt_str:
        raise ValueError("Empty datetime string")
    clean_str = str(dt_str).strip().strip("'\"").replace("Z", "+00:00").replace("z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _unknown_event_error(user_id: int, db: Session, event_id: Any, tool_name: str) -> Dict[str, Any]:
    """Tell the model the id was wrong, and hand it the real ones.

    Picking "the only event this user has" instead would let the assistant edit
    or delete something the user never identified, so the id has to come from
    list_events.
    """
    existing = db.query(Event).filter(Event.user_id == user_id).order_by(Event.start_time.asc()).all()
    return {
        "status": "error",
        "message": (
            f"No event with event_id {event_id!r} belongs to this user. "
            f"Use one of the event_id values below and call {tool_name} again, "
            "or tell the user there is no such event."
        ),
        "existing_events": [
            {"id": ev.id, "title": ev.title, "start_time": ev.start_time.isoformat()}
            for ev in existing
        ],
    }


def create_event_tool(
    user_id: int,
    db: Session,
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    # A malformed timestamp or a missing title is reported back to the model
    # instead of being guessed at: substituting a value would store an event the
    # user never asked for, and hide the bad tool call.
    clean_title = (title or "").strip()
    if not clean_title:
        return {
            "status": "error",
            "message": "title is required. Call create_event again with a short title describing the event.",
        }

    try:
        start_dt = parse_iso_datetime(start_time)
    except Exception:
        return {
            "status": "error",
            "message": f"Could not read start_time {start_time!r}. Pass a full ISO 8601 timestamp such as 2026-06-11T09:00:00Z and call create_event again.",
        }

    if end_time is None or not str(end_time).strip():
        # Documented default: an event with no stated end runs for an hour.
        end_dt = start_dt + timedelta(hours=1)
    else:
        try:
            end_dt = parse_iso_datetime(end_time)
        except Exception:
            return {
                "status": "error",
                "message": f"Could not read end_time {end_time!r}. Pass a full ISO 8601 timestamp such as 2026-06-11T10:00:00Z and call create_event again.",
            }

    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title=clean_title,
        description=description,
        start_time=start_dt,
        end_time=end_dt,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "status": "success",
        "action": "create_event",
        "message": f"Created '{event.title}' starting at {event.start_time.isoformat()}.",
        "event": {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
        },
    }


def update_event_tool(
    user_id: int,
    db: Session,
    event_id: int,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    event = None
    if event_id:
        event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        return _unknown_event_error(user_id, db, event_id, "update_event")

    # Parse before mutating so a bad timestamp leaves the event untouched.
    new_start: Optional[datetime] = None
    new_end: Optional[datetime] = None
    if start_time is not None and start_time.strip():
        try:
            new_start = parse_iso_datetime(start_time)
        except Exception:
            return {
                "status": "error",
                "message": f"Could not read start_time {start_time!r}. Pass a full ISO 8601 timestamp such as 2026-06-15T11:00:00Z and call update_event again.",
            }
    if end_time is not None and end_time.strip():
        try:
            new_end = parse_iso_datetime(end_time)
        except Exception:
            return {
                "status": "error",
                "message": f"Could not read end_time {end_time!r}. Pass a full ISO 8601 timestamp such as 2026-06-15T12:00:00Z and call update_event again.",
            }

    original_duration = event.end_time - event.start_time

    if title is not None and title.strip():
        event.title = title.strip()
    if description is not None:
        event.description = description
    if new_start is not None:
        event.start_time = new_start
    if new_end is not None:
        event.end_time = new_end
    elif new_start is not None:
        # Moved by start time alone: keep the duration the event already had.
        event.end_time = new_start + original_duration

    if event.end_time <= event.start_time:
        event.end_time = event.start_time + timedelta(hours=1)

    db.commit()
    db.refresh(event)

    return {
        "status": "success",
        "action": "update_event",
        "message": f"Updated '{event.title}' successfully.",
        "event": {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
        },
    }


def delete_event_tool(
    user_id: int,
    db: Session,
    event_id: int,
) -> Dict[str, Any]:
    event = None
    if event_id:
        event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        return _unknown_event_error(user_id, db, event_id, "delete_event")

    event_title = event.title
    db.delete(event)
    db.commit()

    return {
        "status": "success",
        "action": "delete_event",
        "message": f"Deleted '{event_title}' from calendar.",
    }


def list_events_tool(
    user_id: int,
    db: Session,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    query = db.query(Event).filter(Event.user_id == user_id)

    if start_time and start_time.strip():
        try:
            start_dt = parse_iso_datetime(start_time)
            query = query.filter(Event.end_time >= start_dt)
        except Exception:
            pass

    if end_time and end_time.strip():
        try:
            end_dt = parse_iso_datetime(end_time)
            query = query.filter(Event.start_time <= end_dt)
        except Exception:
            pass

    if search_query and search_query.strip():
        clean_q = search_query.strip()
        tokens = [w for w in re.findall(r"\w+", clean_q) if len(w) > 1]
        conditions = [
            Event.title.ilike(f"%{clean_q}%"),
            Event.description.ilike(f"%{clean_q}%"),
        ]
        for tok in tokens:
            conditions.append(Event.title.ilike(f"%{tok}%"))
            conditions.append(Event.description.ilike(f"%{tok}%"))
        query = query.filter(or_(*conditions))

    events = query.order_by(Event.start_time.asc()).all()

    return {
        "status": "success",
        "action": "list_events",
        "count": len(events),
        "events": [
            {
                "id": ev.id,
                "title": ev.title,
                "description": ev.description,
                "start_time": ev.start_time.isoformat(),
                "end_time": ev.end_time.isoformat(),
            }
            for ev in events
        ],
    }


class LLMUnavailableError(RuntimeError):
    """Raised when the configured LLM provider is unreachable or misconfigured.

    The chat service intentionally has no keyword-matching fallback. Synthesising
    calendar actions from templates would let a broken LLM path look healthy, so
    failures surface here instead.
    """


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Create a calendar event in the database for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title/name of the event."},
                    "start_time": {"type": "string", "description": "ISO 8601 formatted start datetime (e.g. 2026-06-17T17:00:00Z)."},
                    "end_time": {"type": "string", "description": "ISO 8601 formatted end datetime."},
                    "description": {"type": "string", "description": "Optional notes or event description."}
                },
                "required": ["title", "start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Update or reschedule an existing event in the user's calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The unique integer ID of the event to update."},
                    "title": {"type": "string", "description": "Updated title."},
                    "start_time": {"type": "string", "description": "Updated ISO 8601 start time."},
                    "end_time": {"type": "string", "description": "Updated ISO 8601 end time."},
                    "description": {"type": "string", "description": "Updated description."}
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Cancel or delete an event by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The ID of the event to delete."}
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "List existing calendar events for the user to inspect schedule or find event IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "description": "Optional lower bound ISO 8601 datetime."},
                    "end_time": {"type": "string", "description": "Optional upper bound ISO 8601 datetime."},
                    "search_query": {"type": "string", "description": "Optional search term to filter event titles/descriptions."}
                }
            }
        }
    }
]


def process_chat(
    message: str,
    user_id: int,
    db: Session,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    ref_time = reference_time or datetime.now(timezone.utc)
    provider = (settings.LLM_PROVIDER or "gemini").strip().lower()

    grounding_info = retrieve_relevant_courses(message, db)
    grounding_context_str = grounding_info.get("grounding_text", "")

    gemini_key_present = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())
    if provider == "gemini" and (not gemini_key_present or genai is None):
        missing = "GEMINI_API_KEY is not set" if not gemini_key_present else "the google-generativeai package is not installed"
        raise LLMUnavailableError(
            f"LLM_PROVIDER is 'gemini' but {missing}. "
            "Set GEMINI_API_KEY, install google-generativeai, or set LLM_PROVIDER=ollama."
        )

    now_iso = ref_time.isoformat()
    day_name = ref_time.strftime("%A")

    # The next seven calendar days, resolved for the model. The table ends on the
    # same weekday as today (+7), which is what makes a bare weekday name always
    # land on its next occurrence instead of today.
    upcoming_days = [ref_time + timedelta(days=offset) for offset in range(1, 8)]
    weekday_table = "\n".join(
        f"- {day.strftime('%A')} = {day.strftime('%Y-%m-%d')}" + ("  <- tomorrow" if idx == 0 else "")
        for idx, day in enumerate(upcoming_days)
    )
    next_week_start = (ref_time + timedelta(days=7)).strftime("%Y-%m-%d")
    next_week_end = (ref_time + timedelta(days=13)).strftime("%Y-%m-%d")

    system_instruction = f"""You are the scheduling assistant of a campus app. You manage the user's calendar with the tools you are given, and answer course questions from the verified knowledge base below.

# DATE AND TIME (all times UTC)
Today is {day_name}, {ref_time.strftime('%Y-%m-%d')}. The current time is {now_iso}.
A weekday name always means its NEXT occurrence, given by this table - never today, unless the user literally says "today" or "tonight":
{weekday_table}
"next week" means {next_week_start} to {next_week_end}.
- Convert clock times to 24h: "3pm" -> 15:00, "5pm" -> 17:00, "11am" -> 11:00.
- With no time of day given, use 09:00:00 to 10:00:00 on that date.
- With no duration given, make the event 1 hour. With a duration given, use it exactly: "3pm for 45 minutes" -> 15:00:00 to 15:45:00.
- start_time and end_time are always full ISO 8601 with Z, e.g. "{upcoming_days[0].strftime('%Y-%m-%d')}T09:00:00Z".

# COURSE KNOWLEDGE BASE
{grounding_context_str}

- Facts about courses, codes, syllabi, topics and reviews come ONLY from the block above. Never invent them.
- If it says NO MATCHING COURSES FOUND, say you don't have information on that course.
- If the user asserts a topic the listed syllabus does not contain, do not agree: say the course does not cover it, and state what it does cover.
- A question about a course is answered in words only, with NO tool calls. Mentioning a course they are taking is not a scheduling request.
- Missing course information never blocks a calendar action the user asked for: dropping or moving an event whose title mentions a course is still a plain calendar operation.

# CALENDAR TOOLS
- create_event(title, start_time, end_time, description): any new task, reminder, appointment or deadline. For a deadline, prefix the title with "[Due] ". A deadline the user states as conditional still gets scheduled now.
- list_events(start_time, end_time, search_query): read the calendar, and get the id of an event before changing it.
- update_event(event_id, title, start_time, end_time, description): reschedule or edit. Requires an id from list_events.
- delete_event(event_id): cancel or drop an event. Requires an id from list_events.

# HOW TO ACT
1. Use the fewest calls that satisfy the request, and never repeat a call you have already made with the same arguments.
2. Reschedule or cancel a named event in two steps: list_events(search_query="...") first, then update_event / delete_event with the id you got back.
3. If the user corrects themselves mid-sentence ("...on Friday - wait no, make it Saturday at 4pm instead"), act on the FINAL version ONLY, with exactly one create_event. Never schedule the part they retracted.
4. If the user refers to an event only as "it", "that" or "this" and names no event in this message, call NO tools at all - not even list_events. Reply with a question asking which event they mean.
5. After calling a tool, reply in plain language and name what you found or changed, with its title and time.
6. Small talk and informational questions get no tool calls.
"""

    executed_actions: List[str] = []

    def _record(action: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Record an action only if the tool actually carried it out.

        A rejected call (unknown event_id, unreadable timestamp) is handed back
        to the model so it can correct itself; counting the attempt would report
        a calendar change that never happened.
        """
        if result.get("status") == "success":
            executed_actions.append(action)
        return result

    def create_event(title: str, start_time: str, end_time: str, description: str = "") -> dict:
        return _record("create_event", create_event_tool(user_id, db, title, start_time, end_time, description))

    def update_event(
        event_id: int,
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
    ) -> dict:
        return _record("update_event", update_event_tool(
            user_id,
            db,
            event_id,
            title or None,
            start_time or None,
            end_time or None,
            description or None,
        ))

    def delete_event(event_id: int) -> dict:
        return _record("delete_event", delete_event_tool(user_id, db, event_id))

    def list_events(start_time: str = "", end_time: str = "", search_query: str = "") -> dict:
        return _record(
            "list_events",
            list_events_tool(user_id, db, start_time or None, end_time or None, search_query or None),
        )

    tools = [create_event, update_event, delete_event, list_events]

    def _safe_int(val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    tool_executors = {
        "create_event": lambda **kw: create_event(
            title=str(kw.get("title") or kw.get("name") or kw.get("summary") or ""),
            start_time=str(kw.get("start_time") or kw.get("start") or kw.get("startTime") or ""),
            end_time=str(kw.get("end_time") or kw.get("end") or kw.get("endTime") or ""),
            description=str(kw.get("description") or kw.get("desc") or kw.get("notes") or ""),
        ),
        "update_event": lambda **kw: update_event(
            event_id=_safe_int(kw.get("event_id") or kw.get("id"), 0),
            title=str(kw.get("title") or kw.get("name") or "") if (kw.get("title") or kw.get("name")) else "",
            start_time=str(kw.get("start_time") or kw.get("start") or "") if (kw.get("start_time") or kw.get("start")) else "",
            end_time=str(kw.get("end_time") or kw.get("end") or "") if (kw.get("end_time") or kw.get("end")) else "",
            description=str(kw.get("description") or kw.get("desc") or "") if (kw.get("description") or kw.get("desc")) else "",
        ),
        "delete_event": lambda **kw: delete_event(
            event_id=_safe_int(kw.get("event_id") or kw.get("id"), 0),
        ),
        "list_events": lambda **kw: list_events(
            start_time=str(kw.get("start_time") or kw.get("start") or ""),
            end_time=str(kw.get("end_time") or kw.get("end") or ""),
            search_query=str(kw.get("search_query") or kw.get("query") or kw.get("q") or ""),
        ),
    }

    try:
        from app.services.llm_client import get_llm_client
        client = get_llm_client()
        llm_res = client.generate(
            system_instruction=system_instruction,
            user_message=message,
            tools=tools,
            tool_schemas=TOOL_SCHEMAS,
            tool_executors=tool_executors,
        )

        reply_text = llm_res.reply
        # executed_actions comes from the tool wrappers above, which see whether
        # each call succeeded. llm_res.executed_actions counts attempts instead,
        # so it is only used for logging.
        logger.info(f"Tool calls attempted: {llm_res.executed_actions} | succeeded: {executed_actions}")

        # action_taken reports what the model actually did. A write wins; a bare
        # read counts as a read unless the model used it to look around before
        # asking the user which event they meant, in which case nothing was done.
        asked_for_clarification = "?" in reply_text and any(
            phrase in reply_text.lower()
            for phrase in ["which event", "which one", "which specific", "which course", "clarify", "referring to", "specify"]
        )

        mutating_actions = [a for a in executed_actions if a in ("create_event", "update_event", "delete_event")]
        if mutating_actions:
            action_taken = mutating_actions[-1]
        elif "list_events" in executed_actions and not asked_for_clarification:
            action_taken = "list_events"
        else:
            action_taken = None

        return {
            "reply": reply_text,
            "action_taken": action_taken,
        }
    except LLMUnavailableError:
        raise
    except Exception as e:
        logger.error(f"Error in LLM call: {e}\n{traceback.format_exc()}")
        raise LLMUnavailableError(f"{type(e).__name__}: {e}") from e
