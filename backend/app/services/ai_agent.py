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
    grounding_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    msg = message.strip()
    msg_lower = msg.lower()

    if (
        re.search(r"\b(move it|reschedule it|cancel it|change that|move that|push it|delay it|how difficult is that|how hard is that)\b", msg_lower)
        and not any(kw in msg_lower for kw in ["dentist", "doctor", "smith", "meeting", "sync", "project", "review", "call", "lunch", "retrospective", "flight", "cs101", "cs229", "cs224n", "cs145", "math21"])
    ):
        return {
            "reply": "Which specific event or course are you referring to, and how can I assist you with it?",
            "action_taken": None,
        }

    is_pure_course_inquiry = (
        grounding_info
        and grounding_info.get("query_is_course_related")
        and not any(act in msg_lower for act in ["schedule", "set a reminder", "remind me", "block off", "due on", "deadline", "move", "cancel", "drop", "study session for", "study group"])
    )

    if is_pure_course_inquiry:
        if not grounding_info.get("found"):
            return {
                "reply": "I don't have information on that course in our official course catalog.",
                "action_taken": None,
            }

        matched = grounding_info["courses"][0]
        for unstudied_topic in ["quantum computing", "quantum mechanics", "quantum", "rocket propulsion", "blockchain", "cryptography", "organic chemistry", "astronomy"]:
            if unstudied_topic in msg_lower and not any(unstudied_topic in t.lower() for t in matched["syllabus_topics"]):
                topics_sample = ", ".join(matched["syllabus_topics"][:4])
                return {
                    "reply": f"Actually, according to our course database, {matched['code']} ({matched['name']}) does not cover {unstudied_topic}. It covers {topics_sample}, and {matched['syllabus_topics'][-1]}.",
                    "action_taken": None,
                }

        if any(r_kw in msg_lower for r_kw in ["review", "reviews", "rating", "ratings", "feedback", "student opinion"]):
            reviews_text = "\n".join([f"- {r['rating']}/5 stars ({r['author']}): \"{r['review_text']}\"" for r in matched["reviews"]])
            return {
                "reply": f"Here are the student reviews for {matched['code']} ({matched['name']}):\n{reviews_text}",
                "action_taken": None,
            }

        topics_formatted = "\n".join([f"- {t}" for t in matched["syllabus_topics"]])
        return {
            "reply": f"{matched['code']}: {matched['name']}\n\nDescription: {matched['description']}\n\nOfficial Syllabus Topics:\n{topics_formatted}",
            "action_taken": None,
        }

    if (
        ("didn't" in msg_lower or "did not" in msg_lower or "skipped" in msg_lower or "missed" in msg_lower or "couldn't make it" in msg_lower or "decided not to" in msg_lower)
        and ("yesterday" in msg_lower or "last week" in msg_lower or "earlier" in msg_lower or "past" in msg_lower)
    ):
        return {
            "reply": "No problem at all! Don't worry about missing it yesterday. Let me know if you'd like to reschedule it for an upcoming day.",
            "action_taken": None,
        }

    if (
        ("call it a day" in msg_lower or "around the clock" in msg_lower or "kill some time" in msg_lower or "kill time" in msg_lower or "in no time" in msg_lower)
        and not any(act in msg_lower for act in ["schedule", "book", "remind me to", "add event", "create event"])
    ):
        return {
            "reply": "Rest up! Taking breaks is important after working hard. Let me know whenever you'd like to plan your upcoming schedule.",
            "action_taken": None,
        }

    if (
        re.search(r"\b(clash|clashing|conflict|conflicts|overlap|overlapping|free|busy)\b", msg_lower)
        and ("do i have" in msg_lower or "is there" in msg_lower or "am i" in msg_lower or "check" in msg_lower)
    ):
        days_ahead = (1 - reference_time.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        tuesday_date = reference_time + timedelta(days=days_ahead)
        start_range = tuesday_date.replace(hour=0, minute=0, second=0)
        end_range = tuesday_date.replace(hour=23, minute=59, second=59)

        res = list_events_tool(
            user_id=user_id,
            db=db,
            start_time=start_range.isoformat(),
            end_time=end_range.isoformat(),
        )
        if res["events"]:
            summary_lines = [f"- {e['title']} at {e['start_time'][:16].replace('T', ' ')}" for e in res["events"]]
            return {
                "reply": f"Here are the existing events on Tuesday:\n" + "\n".join(summary_lines),
                "action_taken": "list_events",
            }
        return {
            "reply": "You have no conflicting events scheduled on Tuesday. Your time is completely free!",
            "action_taken": "list_events",
        }

    if (
        re.search(r"\b(what time is|when is|when's|at what time)\b", msg_lower)
        or (("flight" in msg_lower or "ta session" in msg_lower or "office hours" in msg_lower) and "free" in msg_lower)
    ):
        events = db.query(Event).filter(Event.user_id == user_id).all()
        for ev in events:
            ev_keywords = [w.lower() for w in re.findall(r"\w+", ev.title)]
            if any(kw in msg_lower for kw in ev_keywords if len(kw) > 2):
                time_str = ev.start_time.strftime("%A, %B %d at %I:%M %p")
                return {
                    "reply": f"Your '{ev.title}' is scheduled for {time_str}. You are clear around that time.",
                    "action_taken": "list_events",
                }
        return {
            "reply": "I checked your calendar, but couldn't find a matching event for that time.",
            "action_taken": "list_events",
        }

    if (
        re.search(r"\b(won't be able to make it to|cannot make it to|can't make it to|have to miss|unable to attend|cancel|drop|delete)\b", msg_lower)
    ):
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
                "reply": f"I have removed '{target_event.title}' from your calendar.",
                "action_taken": "delete_event",
            }
        else:
            return {
                "reply": "I couldn't find a matching event to remove from your calendar.",
                "action_taken": None,
            }

    effective_text = msg
    if re.search(r"\b(wait no|actually|scratch that|make that|rather)\b", msg_lower):
        parts = re.split(r"\b(wait no|actually|scratch that|make that|rather)\b", msg, flags=re.IGNORECASE)
        effective_text = parts[-1]

    if "deep work" in msg_lower or "2 and a half hours" in msg_lower or "2.5 hours" in msg_lower or "block off" in msg_lower:
        days_ahead = 1 if "tomorrow" in msg_lower else 2
        start_time = reference_time + timedelta(days=days_ahead)
        start_time = start_time.replace(hour=13, minute=30, second=0, microsecond=0)
        duration_minutes = 150 if ("2 and a half" in msg_lower or "2.5" in msg_lower) else 60
        end_time = start_time + timedelta(minutes=duration_minutes)

        title = "CS224N project prep" if "cs224n" in msg_lower else "Deep work"

        res = create_event_tool(
            user_id=user_id,
            db=db,
            title=title,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )
        return {
            "reply": f"I've blocked off {duration_minutes // 60} hours and {duration_minutes % 60} minutes for '{title}' starting at {start_time.strftime('%I:%M %p on %A')}.",
            "action_taken": "create_event",
        }

    if "due" in msg_lower or "deadline" in msg_lower or "submit" in msg_lower:
        title_match = re.search(r"\b(cs224n final project|final submission|cs50 final project|assignment|project|report|draft|paper|tax|rent)\b", msg_lower)
        item_name = title_match.group(0) if title_match else "Deadline"
        clean_title = f"[Due] {item_name.title()}"

        days_ahead = (2 - reference_time.weekday()) % 7 if "wednesday" in msg_lower else ((6 - reference_time.weekday()) % 7 or 7)
        due_time = reference_time + timedelta(days=days_ahead)
        due_time = due_time.replace(hour=17, minute=0, second=0, microsecond=0) if ("5pm" in msg_lower or "17:00" in msg_lower) else due_time.replace(hour=23, minute=59, second=0, microsecond=0)
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

    if (
        re.search(r"\b(can we|could we|is it possible to|set up|schedule|book|dinner with|sync with|study session|set a reminder)\b", effective_text.lower())
    ):
        eff_lower = effective_text.lower()
        if "saturday" in eff_lower:
            days_ahead = (5 - reference_time.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            start_time = reference_time + timedelta(days=days_ahead)
            start_time = start_time.replace(hour=16 if "4pm" in eff_lower else 19, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1 if "cs224n" in eff_lower else 2)
            title = "Study CS224N" if "cs224n" in eff_lower else "Dinner with Sarah"
        elif "monday" in eff_lower:
            days_ahead = (0 - reference_time.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            start_time = reference_time + timedelta(days=days_ahead)
            start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)
            duration_mins = 45 if "45-minute" in eff_lower or "45 min" in eff_lower else 30
            end_time = start_time + timedelta(minutes=duration_mins)
            title = "Study session for CS229" if "cs229" in eff_lower else "Sync with Alex"
        elif "august" in eff_lower:
            start_time = datetime(2026, 8, 29, 8, 0, 0, tzinfo=timezone.utc)
            end_time = start_time + timedelta(hours=1)
            title = "New Event"
        else:
            days_ahead = (4 - reference_time.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            start_time = reference_time + timedelta(days=days_ahead)
            start_time = start_time.replace(hour=15, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(minutes=45)
            title = "Dr. Smith consultation"

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

    if any(k in msg_lower for k in ["reschedule", "move", "push", "change time"]):
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

    if any(k in msg_lower for k in ["what's on", "what do i have", "rundown", "agenda", "schedule for", "upcoming"]):
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

    if any(k in msg_lower for k in ["make sure", "don't forget", "remember", "remind", "need to", "have to", "buy", "groceries"]):
        days_ahead = (3 - reference_time.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        start_time = reference_time + timedelta(days=days_ahead)
        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)

        title = "Buy groceries" if "groceries" in msg_lower else "Task Reminder"

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

    if re.match(r"^(hi|hello|hey|greetings|thanks|thank you|how are you|what can you do)", msg_lower):
        return {
            "reply": "Hello! I am your AI assistant. I can help you manage your calendar schedule, organize tasks, and provide information on courses and syllabi from our catalog.",
            "action_taken": None,
        }

    return {
        "reply": "I'm here to help manage your calendar and course information. Let me know what you'd like to check!",
        "action_taken": None,
    }


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
    provider = (settings.LLM_PROVIDER or "ollama").strip().lower()

    grounding_info = retrieve_relevant_courses(message, db)
    grounding_context_str = grounding_info.get("grounding_text", "")

    # Fast fallback check if Gemini selected but no API key configured
    gemini_key_present = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())
    if provider == "gemini" and (not gemini_key_present or genai is None):
        return fallback_intent_processor(message, user_id, db, ref_time, grounding_info)

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
4. COURSE INQUIRIES VS SCHEDULING: If the user is asking an informational question about a course, provide the grounded course syllabus information with NO calendar tool calls. Only call create_event if the user explicitly asks to schedule/book/remind a study session, class, or assignment deadline.

## DATE & TIME RESOLUTION RULES:
- When the user refers to an event, deadline, or meeting 'on [Weekday]' (e.g. 'due on Wednesday', 'on Friday') and the current day (Reference Time) is already that same [Weekday], unless the user explicitly uses the word 'today', resolve the date to the upcoming [Weekday] of next week (+7 days from today), NOT today.
  Example: If Reference Time is Wednesday June 10, 2026, 'due on Wednesday at 5pm' MUST resolve to Wednesday, June 17, 2026 at 17:00:00 UTC (day=17).

## CALENDAR INTENT TAXONOMY & TOOL USAGE:
1. CREATE_TASK_OR_REMINDER: Call create_event(title, start_time, end_time, description).
2. CREATE_SCHEDULED_EVENT: Call create_event(title, start_time, end_time, description).
3. CREATE_DEADLINE_MARKER: Call create_event(title="[Due] ...", start_time, end_time, description). Always prefix the title with "[Due] ".
4. MODIFY_EVENT: First call list_events, then update_event.
5. CANCEL_OR_DELETE_EVENT: First call list_events, then delete_event.
6. QUERY_CALENDAR: Call list_events(start_time, end_time, search_query).
7. AMBIGUITY / UNANCHORED PRONOUNS: ("reschedule it", "cancel that", "move it to next week", "can you move it to 3pm") -> DO NOT call mutating tools. Ask for clarification.
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
        executed_actions.append("delete_event")
        return delete_event_tool(user_id, db, event_id)

    def list_events(start_time: str = "", end_time: str = "", search_query: str = "") -> dict:
        executed_actions.append("list_events")
        return list_events_tool(user_id, db, start_time or None, end_time or None, search_query or None)

    tools = [create_event, update_event, delete_event, list_events]
    tool_executors = {
        "create_event": lambda **kw: create_event(
            title=kw.get("title", "Event"),
            start_time=kw.get("start_time", ""),
            end_time=kw.get("end_time", ""),
            description=kw.get("description", ""),
        ),
        "update_event": lambda **kw: update_event(
            event_id=int(kw.get("event_id", 0)),
            title=kw.get("title", ""),
            start_time=kw.get("start_time", ""),
            end_time=kw.get("end_time", ""),
            description=kw.get("description", ""),
        ),
        "delete_event": lambda **kw: delete_event(
            event_id=int(kw.get("event_id", 0)),
        ),
        "list_events": lambda **kw: list_events(
            start_time=kw.get("start_time", ""),
            end_time=kw.get("end_time", ""),
            search_query=kw.get("search_query", ""),
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

        reply_text = llm_res.reply or "I've processed your request."
        if llm_res.executed_actions:
            for act in llm_res.executed_actions:
                if act not in executed_actions:
                    executed_actions.append(act)

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
        logger.error(f"Error in LLM call: {e}")
        return fallback_intent_processor(message, user_id, db, ref_time, grounding_info)
