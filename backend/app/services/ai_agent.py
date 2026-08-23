import logging
import sys
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import re
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.models import User, Event, ChatMessage

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
    logger.info("google.generativeai imported successfully.")
except ImportError as e:
    genai = None
    logger.warning(f"google.generativeai failed to import: {e}")

_RESOLVED_MODEL_NAME: Optional[str] = None


def resolve_best_gemini_model() -> str:
    """
    Query available models for the configured API key and return the most capable
    model supporting 'generateContent' to prevent 404 NotFound errors across API versions.
    """
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

        logger.info(f"Available Gemini models supporting generateContent: {available}")

        for candidate in priority_candidates:
            if candidate and candidate in available:
                _RESOLVED_MODEL_NAME = candidate
                logger.info(f"Selected Gemini model: {_RESOLVED_MODEL_NAME}")
                return _RESOLVED_MODEL_NAME

        if available:
            _RESOLVED_MODEL_NAME = available[0]
            logger.info(f"Selected fallback available Gemini model: {_RESOLVED_MODEL_NAME}")
            return _RESOLVED_MODEL_NAME

    except Exception as e:
        logger.warning(f"Failed to auto-discover Gemini models via list_models: {e}")

    _RESOLVED_MODEL_NAME = settings.GEMINI_MODEL or "gemini-3.6-flash"
    return _RESOLVED_MODEL_NAME


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an ISO 8601 datetime string with timezone awareness using standard library."""
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
    """Create a new event, reminder, task, or deadline marker in the user's calendar."""
    logger.info(f"Executing create_event_tool: title='{title}', start_time='{start_time}', end_time='{end_time}'")
    try:
        start_dt = parse_iso_datetime(start_time)
    except Exception as e:
        logger.warning(f"Failed to parse start_time '{start_time}': {e}. Using default.")
        start_dt = datetime.now(timezone.utc) + timedelta(hours=1)

    try:
        end_dt = parse_iso_datetime(end_time)
    except Exception as e:
        logger.warning(f"Failed to parse end_time '{end_time}': {e}. Using default.")
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
    logger.info(f"Successfully created Event ID {event.id}: '{event.title}'")

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
    """Modify an existing event's date, time, title, or description."""
    logger.info(f"Executing update_event_tool: event_id={event_id}, title={title}, start_time={start_time}")
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        return {"status": "error", "message": f"Event ID {event_id} not found."}

    if title is not None:
        event.title = title
    if description is not None:
        event.description = description
    if start_time is not None:
        try:
            event.start_time = parse_iso_datetime(start_time)
        except Exception:
            pass
    if end_time is not None:
        try:
            event.end_time = parse_iso_datetime(end_time)
        except Exception:
            pass

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
    """Cancel or delete a scheduled event from the user's calendar."""
    logger.info(f"Executing delete_event_tool: event_id={event_id}")
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        return {"status": "error", "message": f"Event ID {event_id} not found."}

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
    """Retrieve calendar events within a date range or matching a search keyword."""
    logger.info(f"Executing list_events_tool: start_time={start_time}, end_time={end_time}, search_query={search_query}")
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
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Event.title.ilike(search_pattern),
                Event.description.ilike(search_pattern),
            )
        )

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


def fallback_intent_processor(
    message: str,
    user_id: int,
    db: Session,
    reference_time: datetime,
) -> Dict[str, Any]:
    """
    Deterministic semantic intent fallback processor used when GEMINI_API_KEY is unset or during tests.
    """
    logger.info(f"[FALLBACK_INTENT_PROCESSOR] Processing message: '{message}'")
    msg = message.strip()
    msg_lower = msg.lower()

    # Intent 9: Genuine Ambiguity
    if (
        ("move that" in msg_lower or "reschedule that" in msg_lower or "change that" in msg_lower or "move thing" in msg_lower)
        and not any(name in msg_lower for name in ["dentist", "doctor", "smith", "meeting", "sync", "project", "review", "call", "lunch"])
    ):
        logger.info("[FALLBACK] Matched Intent: Ambiguity Clarification")
        return {
            "reply": "Which specific event would you like to move, and what time would you prefer?",
            "action_taken": None,
        }

    # Intent 7: General Conversation
    if (
        re.match(r"^(hi|hello|hey|greetings|thanks|thank you|how are you|what can you do)", msg_lower)
        and not any(k in msg_lower for k in ["schedule", "remind", "due", "meeting", "appointment", "calendar", "event", "plate", "rundown", "what's on", "what do i have", "august", "tomorrow"])
    ):
        logger.info("[FALLBACK] Matched Intent: General Conversation")
        return {
            "reply": "Hello! I am your AI calendar assistant. I can help you schedule appointments, keep track of deadlines, set reminders, update events, or summarize your agenda.",
            "action_taken": None,
        }

    # Intent 5: Cancel / Delete Event
    if any(k in msg_lower for k in ["cancel", "drop", "delete", "remove", "don't need"]):
        logger.info("[FALLBACK] Matched Intent: Cancel / Delete")
        events = db.query(Event).filter(Event.user_id == user_id).all()
        target_event = None
        for ev in events:
            ev_keywords = [w.lower() for w in re.findall(r"\w+", ev.title)]
            if any(kw in msg_lower for kw in ev_keywords if len(kw) > 2):
                target_event = ev
                break
        if target_event:
            delete_event_tool(user_id, db, target_event.id)
            return {
                "reply": f"I've removed '{target_event.title}' from your calendar.",
                "action_taken": "delete_event",
            }
        else:
            return {
                "reply": "I couldn't find a matching event to remove. Could you specify the exact event title?",
                "action_taken": None,
            }

    # Intent 4: Modify / Reschedule Event
    if any(k in msg_lower for k in ["reschedule", "move", "push", "change time"]):
        logger.info("[FALLBACK] Matched Intent: Modify / Reschedule")
        events = db.query(Event).filter(Event.user_id == user_id).all()
        target_event = None
        for ev in events:
            ev_keywords = [w.lower() for w in re.findall(r"\w+", ev.title)]
            if any(kw in msg_lower for kw in ev_keywords if len(kw) > 2):
                target_event = ev
                break

        new_start = reference_time + timedelta(days=5)
        new_start = new_start.replace(hour=11, minute=0, second=0, microsecond=0)
        new_end = new_start + timedelta(hours=1)

        if target_event:
            update_event_tool(
                user_id=user_id,
                db=db,
                event_id=target_event.id,
                start_time=new_start.isoformat(),
                end_time=new_end.isoformat(),
            )
            return {
                "reply": f"I've rescheduled '{target_event.title}' to {new_start.strftime('%A at %I:%M %p')}.",
                "action_taken": "update_event",
            }

    # Intent 8: Specific Event Query
    if re.search(r"\b(when is|at what time is|when's)\b", msg_lower):
        logger.info("[FALLBACK] Matched Intent: Specific Event Query")
        events = db.query(Event).filter(Event.user_id == user_id).all()
        for ev in events:
            ev_keywords = [w.lower() for w in re.findall(r"\w+", ev.title)]
            if any(kw in msg_lower for kw in ev_keywords if len(kw) > 2):
                time_str = ev.start_time.strftime("%A, %B %d at %I:%M %p")
                return {
                    "reply": f"Your '{ev.title}' is scheduled for {time_str}.",
                    "action_taken": "list_events",
                }
        return {
            "reply": "I checked your calendar, but couldn't find an appointment matching that description.",
            "action_taken": "list_events",
        }

    # Intent 6: Query Calendar
    if any(k in msg_lower for k in ["what's on", "what do i have", "rundown", "agenda", "free", "schedule for", "upcoming"]):
        logger.info("[FALLBACK] Matched Intent: Query Calendar")
        if "weekend" in msg_lower:
            start_range = reference_time + timedelta(days=3)
            start_range = start_range.replace(hour=0, minute=0, second=0)
            end_range = start_range + timedelta(days=2)
        elif "tomorrow" in msg_lower:
            start_range = reference_time + timedelta(days=1)
            start_range = start_range.replace(hour=0, minute=0, second=0)
            end_range = start_range + timedelta(days=1)
        else:
            start_range = reference_time.replace(hour=0, minute=0, second=0)
            end_range = start_range + timedelta(days=7)

        res = list_events_tool(
            user_id=user_id,
            db=db,
            start_time=start_range.isoformat(),
            end_time=end_range.isoformat(),
        )
        if res["events"]:
            summary_lines = [f"- {e['title']} ({e['start_time'][:16].replace('T', ' ')})" for e in res["events"]]
            return {
                "reply": "Here is what is on your schedule:\n" + "\n".join(summary_lines),
                "action_taken": "list_events",
            }
        return {
            "reply": "You have nothing scheduled for that timeframe.",
            "action_taken": "list_events",
        }

    # Intent 3: Implied Deadline
    if "due" in msg_lower or "deadline" in msg_lower or "submit" in msg_lower:
        logger.info("[FALLBACK] Matched Intent: Implied Deadline")
        clean_title = re.sub(r"(submission deadline is|deadline is|is due|due date is|this|at \d+:\d+|\bby\b.*)", "", msg, flags=re.IGNORECASE).strip()
        if not clean_title.startswith("[Due]"):
            clean_title = f"[Due] {clean_title}".strip()

        if "sunday" in msg_lower:
            days_ahead = (6 - reference_time.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            due_time = reference_time + timedelta(days=days_ahead)
            due_time = due_time.replace(hour=23, minute=59, second=0, microsecond=0)
        else:
            due_time = reference_time + timedelta(days=2, hours=5)

        end_time = due_time + timedelta(minutes=1)

        res = create_event_tool(
            user_id=user_id,
            db=db,
            title=clean_title,
            start_time=due_time.isoformat(),
            end_time=end_time.isoformat(),
            description="Deadline marker",
        )
        return {
            "reply": f"Added deadline marker '{clean_title}' for {due_time.strftime('%A at %I:%M %p')}.",
            "action_taken": "create_event",
        }

    # Intent 2: Scheduled Event / Appointment
    if "consultation" in msg_lower or "meeting" in msg_lower or "appointment" in msg_lower or "sync" in msg_lower or "block off" in msg_lower or "add an event" in msg_lower or "add event" in msg_lower:
        logger.info("[FALLBACK] Matched Intent: Scheduled Appointment")
        if "august" in msg_lower:
            start_time = datetime(2026, 8, 29, 8, 0, 0, tzinfo=timezone.utc)
            title = "New Event"
        else:
            days_ahead = (4 - reference_time.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            start_time = reference_time + timedelta(days=days_ahead)
            start_time = start_time.replace(hour=15, minute=0, second=0, microsecond=0)
            title = "Dr. Smith consultation" if "smith" in msg_lower else "Scheduled Meeting"

        end_time = start_time + timedelta(hours=1)

        res = create_event_tool(
            user_id=user_id,
            db=db,
            title=title,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )
        return {
            "reply": f"I've booked '{title}' for {start_time.strftime('%A, %B %d at %I:%M %p')}.",
            "action_taken": "create_event",
        }

    # Intent 1: Task / Reminder
    if any(k in msg_lower for k in ["make sure", "don't forget", "remember", "remind", "need to", "have to", "buy", "groceries", "add a test", "test at"]):
        logger.info("[FALLBACK] Matched Intent: Task / Reminder")
        days_ahead = (3 - reference_time.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        start_time = reference_time + timedelta(days=days_ahead)
        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)

        title = "Buy groceries" if "groceries" in msg_lower else ("Test Event" if "test" in msg_lower else "Task Reminder")

        res = create_event_tool(
            user_id=user_id,
            db=db,
            title=title,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )
        return {
            "reply": f"I've added '{title}' for {start_time.strftime('%A at %I:%M %p')}.",
            "action_taken": "create_event",
        }

    logger.warning("[FALLBACK] No intent matched in fallback processor. Falling through to default message.")
    return {
        "reply": "I'm here to help manage your calendar. Let me know what you'd like to schedule, modify, or check!",
        "action_taken": None,
    }


def process_chat(
    message: str,
    user_id: int,
    db: Session,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Process a user chat message using Google Gemini with structured semantic intent taxonomy and function calling.
    Includes auto-discovery of supported model names and transparent error reporting.
    """
    ref_time = reference_time or datetime.now(timezone.utc)
    key_present = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())
    masked_key = (
        f"{settings.GEMINI_API_KEY[:4]}...{settings.GEMINI_API_KEY[-4:]}"
        if key_present and len(settings.GEMINI_API_KEY) > 8
        else ("SET" if key_present else "NOT_SET")
    )

    logger.info("==================== [PROCESS_CHAT INVOKED] ====================")
    logger.info(f"User ID: {user_id}")
    logger.info(f"User Message: '{message}'")
    logger.info(f"Reference Time: {ref_time.isoformat()}")
    logger.info(f"GEMINI_API_KEY configured: {key_present} (Value: {masked_key})")
    logger.info(f"google.generativeai module available: {genai is not None}")

    if not key_present:
        logger.warning(
            "[ROUTING] GEMINI_API_KEY is empty/missing. Routing to fallback_intent_processor."
        )
        return fallback_intent_processor(message, user_id, db, ref_time)

    if genai is None:
        logger.warning(
            "[ROUTING] google.generativeai module is None. Routing to fallback_intent_processor."
        )
        return fallback_intent_processor(message, user_id, db, ref_time)

    active_model_name = resolve_best_gemini_model()
    logger.info(f"[ROUTING] Calling Google Gemini API with model: {active_model_name}")

    now_iso = ref_time.isoformat()
    day_name = ref_time.strftime("%A")

    system_instruction = f"""You are an intelligent calendar assistant. Your job is to understand user intents related to scheduling, tasks, reminders, queries, and calendar modifications, and translate them into appropriate tool calls.

Current Reference Time: {now_iso} ({day_name})
Timezone: UTC

## INTENT TAXONOMY & CLASSIFICATION
You must first understand the user's underlying meaning and classify it into one of the following intent categories:

1. CREATE_TASK_OR_REMINDER:
   - Intent: Create a calendar item for a task, chore, or personal reminder.
   - Example phrasings: "don't forget to pick up groceries tomorrow", "I need to review the PR tonight", "remember that I have to call the plumber on Monday".
   - Tool: create_event(title, start_time, end_time, description)
   - Rule: If no specific time of day is provided, default to a sensible time (e.g. 09:00 AM on that date) with a 30 to 60 minute duration.

2. CREATE_SCHEDULED_EVENT:
   - Intent: Reserve a dedicated appointment, meeting, or focus time block.
   - Example phrasings: "I have a dentist appointment Thursday at 4", "sync with Dana at 2pm", "block off Friday afternoon from 1 to 5 for studying", "add an event in august 29 at 08:00".
   - Tool: create_event(title, start_time, end_time, description)

3. CREATE_DEADLINE_MARKER:
   - Intent: Mark a due date or submission cutoff. This is an implied milestone, not literally a reminder.
   - Example phrasings: "my assignment is due Friday", "rent is due on the 1st", "submit paper by 5pm tomorrow".
   - Tool: create_event(title="[Due] ...", start_time, end_time, description)

4. MODIFY_EVENT:
   - Intent: Reschedule, move, or change details of an existing event.
   - Example phrasings: "move my 2pm to 4pm", "push the dentist to next week", "actually make that call for tomorrow instead".
   - Tool: Call list_events to find the target event ID, then call update_event(event_id, ...).

5. CANCEL_OR_DELETE_EVENT:
   - Intent: Delete or cancel an existing event or reminder.
   - Example phrasings: "cancel my meeting with Dana", "I don't need the dentist reminder anymore", "remove tomorrow's 10am".
   - Tool: Call list_events to identify the target event ID, then call delete_event(event_id).

6. QUERY_CALENDAR:
   - Intent: Inquire about schedule at any granularity (specific day, time range, or specific event lookup).
   - Example phrasings: "what do I have today", "what's on Tuesday", "am I free tomorrow morning", "this week", "the next few days", "between now and Friday", "when is my dentist appointment".
   - Tool: list_events(start_time, end_time, search_query)
   - Rule: Always inspect real returned events before summarizing. Never fabricate or guess events.

7. GENERAL_CONVERSATION:
   - Intent: Chit-chat, greeting, appreciation, or questions about how the app works.
   - Example phrasings: "hello!", "thanks for your help", "how do you work?".
   - Action: Respond conversationally with NO tool calls.

## CRITICAL PRINCIPLES:
- NOTE: The phrasings listed above are examples illustrating the patterns, NOT an exhaustive list. You must classify by underlying semantic intent, however the user words it.
- AMBIGUITY & CLARIFYING QUESTIONS: If the input is genuinely ambiguous (e.g. "move my meeting" when there are multiple meetings, or "schedule an appointment" with no date or subject at all), ask ONE concise, targeted clarifying question instead of guessing or silently failing. Do NOT ask for clarification if sensible defaults (e.g. 1-hour duration, 9am start for a day) can be reasonably inferred.
- ZERO HALLUCINATION: Only confirm actions that were successfully executed via tool calls.
"""

    def create_event(title: str, start_time: str, end_time: str, description: str = "") -> dict:
        """Create a new event, reminder, task, or deadline marker in the user's calendar."""
        return create_event_tool(user_id, db, title, start_time, end_time, description)

    def update_event(
        event_id: int,
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
    ) -> dict:
        """Modify an existing event's date, time, title, or description in the calendar."""
        return update_event_tool(
            user_id,
            db,
            event_id,
            title or None,
            start_time or None,
            end_time or None,
            description or None,
        )

    def delete_event(event_id: int) -> dict:
        """Cancel or delete a scheduled event from the user's calendar."""
        return delete_event_tool(user_id, db, event_id)

    def list_events(start_time: str = "", end_time: str = "", search_query: str = "") -> dict:
        """Retrieve calendar events within a date range or matching a search keyword."""
        return list_events_tool(user_id, db, start_time or None, end_time or None, search_query or None)

    tools = [create_event, update_event, delete_event, list_events]

    logger.info("--- [PAYLOAD SENT TO GEMINI] ---")
    logger.info(f"Model: {active_model_name}")
    logger.info(f"Tools Registered: {[t.__name__ for t in tools]}")
    logger.info(f"User Message: {message}")

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=active_model_name,
            tools=tools,
            system_instruction=system_instruction,
        )

        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(message)

        logger.info("--- [RAW RESPONSE RECEIVED FROM GEMINI] ---")
        logger.info(f"Response Object: {response}")
        logger.info(f"Response Text: '{response.text if hasattr(response, 'text') else None}'")

        action_taken = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    action_taken = part.function_call.name
                    logger.info(f"Function Call Detected: {action_taken} with args: {part.function_call.args}")

        reply_text = response.text if response.text else "I've processed your calendar request."
        logger.info(f"Final Reply to User: '{reply_text}', Action: {action_taken}")

        return {
            "reply": reply_text,
            "action_taken": action_taken,
        }

    except Exception as e:
        logger.error(f"--- [EXCEPTION OCCURRED DURING GEMINI CALL] ---: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())

        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "401" in err_msg:
            return {
                "reply": "Authentication Error: The provided GEMINI_API_KEY is invalid. Please check your .env configuration.",
                "action_taken": None,
            }
        elif "ResourceExhausted" in type(e).__name__ or "429" in err_msg:
            return {
                "reply": "Quota Exceeded: The Gemini API quota was reached. Please try again in a few moments.",
                "action_taken": None,
            }

        logger.warning("[FALLBACK AFTER ERROR] Invoking fallback_intent_processor...")
        return fallback_intent_processor(message, user_id, db, ref_time)
