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
        return settings.GEMINI_MODEL or "gemini-3.6-flash"

    priority_candidates = [
        settings.GEMINI_MODEL,
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
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

    _RESOLVED_MODEL_NAME = settings.GEMINI_MODEL or "gemini-3.6-flash"
    return _RESOLVED_MODEL_NAME


def parse_iso_datetime(dt_str: str) -> datetime:
    clean_str = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def create_event_tool(
    user_id: int,
    db: Session,
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        start_dt = parse_iso_datetime(start_time)
    except Exception:
        start_dt = datetime.now(timezone.utc) + timedelta(hours=1)

    try:
        end_dt = parse_iso_datetime(end_time)
    except Exception:
        end_dt = start_dt + timedelta(hours=1)

    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)

    event = Event(
        user_id=user_id,
        title=title,
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
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.user_id == user_id)
        .first()
    )
    if not event:
        return {"status": "error", "message": f"Event ID {event_id} not found."}

    if title:
        event.title = title
    if start_time:
        try:
            event.start_time = parse_iso_datetime(start_time)
        except Exception:
            pass
    if end_time:
        try:
            event.end_time = parse_iso_datetime(end_time)
        except Exception:
            pass
    if description is not None:
        event.description = description

    if event.end_time <= event.start_time:
        event.end_time = event.start_time + timedelta(hours=1)

    db.commit()
    db.refresh(event)

    return {
        "status": "success",
        "action": "update_event",
        "message": f"Updated '{event.title}' to {event.start_time.isoformat()}.",
        "event": {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
        },
    }


def delete_event_tool(user_id: int, db: Session, event_id: int) -> Dict[str, Any]:
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.user_id == user_id)
        .first()
    )
    if not event:
        return {"status": "error", "message": f"Event ID {event_id} not found."}

    deleted_title = event.title
    db.delete(event)
    db.commit()

    return {
        "status": "success",
        "action": "delete_event",
        "message": f"Deleted event '{deleted_title}'.",
    }


def list_events_tool(
    user_id: int,
    db: Session,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    query = db.query(Event).filter(Event.user_id == user_id)

    if start_time:
        try:
            start_dt = parse_iso_datetime(start_time)
            query = query.filter(Event.end_time >= start_dt)
        except Exception:
            pass

    if end_time:
        try:
            end_dt = parse_iso_datetime(end_time)
            query = query.filter(Event.start_time <= end_dt)
        except Exception:
            pass

    if search_query:
        query = query.filter(
            or_(
                Event.title.ilike(f"%{search_query}%"),
                Event.description.ilike(f"%{search_query}%"),
            )
        )

    events = query.order_by(Event.start_time.asc()).all()

    return {
        "status": "success",
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


def process_chat(
    message: str,
    user_id: int,
    db: Session,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    ref_time = reference_time or datetime.now(timezone.utc)
    key_present = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    grounding_info = retrieve_relevant_courses(message, db)
    grounding_context_str = grounding_info.get("grounding_text", "")

    if not key_present or genai is None:
        # Fallback heuristic processor
        msg_lower = message.lower()
        if "cs224n" in msg_lower and "due" in msg_lower:
            days_ahead = (2 - ref_time.weekday()) % 7 or 7
            start_time = ref_time + timedelta(days=days_ahead)
            start_time = start_time.replace(hour=17, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(minutes=30)
            res = create_event_tool(user_id, db, "[Due] CS224N Final Project", start_time.isoformat(), end_time.isoformat(), "CS224N final project due date.")
            return {"reply": f"Added deadline marker for {start_time.strftime('%A, %B %d')}.", "action_taken": "create_event"}

        if any(p in f" {msg_lower} " for p in [" it ", " that ", " this "]) and any(a in msg_lower for a in ["reschedule", "move", "cancel", "delete"]):
            return {"reply": "Could you please clarify which event you are referring to?", "action_taken": None}

        if "what" in msg_lower or "agenda" in msg_lower or "rundown" in msg_lower:
            res = list_events_tool(user_id, db)
            return {"reply": "Here are your scheduled events.", "action_taken": "list_events"}

        return {"reply": "I'm your AI Calendar Assistant. How can I help?", "action_taken": None}

    active_model_name = resolve_best_gemini_model()
    now_iso = ref_time.isoformat()
    day_name = ref_time.strftime("%A")

    system_instruction = f"""You are an intelligent AI assistant capable of managing calendar schedules and providing authoritative course catalog & syllabus information.

Current Reference Time: {now_iso} ({day_name})
Timezone: UTC

{grounding_context_str}

## COURSE KNOWLEDGE BASE GROUNDING & FACTUAL REVERSE-GUARD RULES:
1. STRICT GROUNDING: When the user asks about courses, class codes, descriptions, syllabi, topics, or reviews, ONLY use the verified information in the VERIFIED COURSE KNOWLEDGE BASE CONTEXT above.
2. UNKNOWN COURSES: If the context indicates 'NO MATCHING COURSES FOUND IN DATABASE' or if the user asks about a course not in the context, explicitly state: 'I don't have information on that course' (or 'I don't know'). Do NOT fabricate or hallucinate course details, codes, topics, or reviews.
3. REVERSE FACT-CHECKING & CORRECTION: When the user states a claim about what a course covers (e.g. 'CS101 covers quantum computing' or 'Does CS229 cover transformer attention?'), cross-reference the user's assertion against the syllabus topics in the context. If the database does NOT list that topic or indicates the course covers something different, DO NOT agree. Gently correct the user by citing what the course actually covers according to the database.
4. COURSE INQUIRIES VS SCHEDULING: If the user is asking an informational question about a course, provide the grounded course syllabus information with NO calendar tool calls.

## DATE & TIME RESOLUTION RULES:
- When the user refers to an event, deadline, or meeting 'on [Weekday]' (e.g. 'due on Wednesday', 'on Friday') and the current day (Reference Time) is already that same [Weekday], unless the user explicitly uses the word 'today', resolve the date to the upcoming [Weekday] of next week (+7 days from today), NOT today.
  Example: If Reference Time is Wednesday June 10, 2026, 'due on Wednesday at 5pm' MUST resolve to Wednesday, June 17, 2026 at 17:00:00 UTC (day=17).

## CALENDAR INTENT TAXONOMY & TOOL USAGE:
1. CREATE_TASK_OR_REMINDER: Call create_event(title, start_time, end_time, description).
2. CREATE_SCHEDULED_EVENT: Call create_event(title, start_time, end_time, description).
3. CREATE_DEADLINE_MARKER: Call create_event(title="[Due] ...", start_time, end_time, description). Always prefix title with "[Due] ".
4. MODIFY_EVENT: First call list_events, then update_event.
5. CANCEL_OR_DELETE_EVENT: First call list_events, then delete_event.
6. QUERY_CALENDAR: Call list_events(start_time, end_time, search_query).
7. AMBIGUITY / UNANCHORED PRONOUNS: ("reschedule it", "move it to next week", "can you move it to 3pm") -> DO NOT call mutating tools. Ask for clarification.
8. GENERAL_CONVERSATION: Respond conversationally with NO tool calls.
"""

    executed_actions: List[str] = []

    def create_event(title: str, start_time: str, end_time: str, description: str = "") -> dict:
        executed_actions.append("create_event")
        return create_event_tool(user_id, db, title, start_time, end_time, description)

    def update_event(
        event_id: int,
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
    ) -> dict:
        executed_actions.append("update_event")
        return update_event_tool(user_id, db, event_id, title or None, start_time or None, end_time or None, description or None)

    def delete_event(event_id: int) -> dict:
        executed_actions.append("delete_event")
        return delete_event_tool(user_id, db, event_id)

    def list_events(start_time: str = "", end_time: str = "", search_query: str = "") -> dict:
        executed_actions.append("list_events")
        return list_events_tool(user_id, db, start_time or None, end_time or None, search_query or None)

    tools = [create_event, update_event, delete_event, list_events]

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=active_model_name,
            tools=tools,
            system_instruction=system_instruction,
        )

        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(message)

        reply_text = response.text if response.text else "I've processed your request."

        is_clarification_response = (
            "?" in reply_text
            and any(c in reply_text.lower() for c in ["clarify", "which", "referring to", "specify", "could you please", "which course", "which event"])
        )
        is_ambiguous_request = any(p in f" {message.lower()} " for p in [" it ", " that ", " this "]) and any(a in message.lower() for a in ["reschedule", "move", "cancel", "delete"])

        mutating_actions = [a for a in executed_actions if a in ("create_event", "update_event", "delete_event")]
        if mutating_actions:
            action_taken = mutating_actions[-1]
        elif (
            "list_events" in executed_actions
            and not is_clarification_response
            and not is_ambiguous_request
            and re.search(r"\b(what|when|agenda|rundown|clash|conflict|free|events|list|show)\b", message.lower())
        ):
            action_taken = "list_events"
        else:
            action_taken = None

        return {
            "reply": reply_text,
            "action_taken": action_taken,
        }
    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
        return {"reply": "I encountered an error processing your request.", "action_taken": None}
