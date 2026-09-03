"""Wall-clock ↔ instant conversion for the assistant.

The database stores instants in UTC and the browser renders them in the reader's
zone, which is right and needs no help. The AI path is where a zone has to be
chosen explicitly, because a user says "6pm" and means 6pm *where they are* —
the model has to be told which wall clock that is, and what it writes has to be
converted back to an instant the same way.

Getting this wrong is silent: the event lands in the database, the reply says
"6pm", and the calendar shows a different hour. That is the bug this module
exists to prevent.

Everything here is total: an unknown or malformed zone name falls back rather
than raising, because a scheduling request should not fail over a bad header.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

try:  # Python 3.9+
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - the containers are 3.12
    ZoneInfo = None  # type: ignore[assignment]

    class ZoneInfoNotFoundError(Exception):  # type: ignore[no-redef]
        pass


from app.core.config import settings

logger = logging.getLogger("timezones")

UTC = timezone.utc


def resolve_timezone(*candidates: Optional[str]) -> timezone:
    """First usable IANA zone from `candidates`, else the configured default.

    Called with the most specific source first, e.g.
    `resolve_timezone(request_timezone, user.timezone)` — the browser knows where
    the user is *now*, the stored value is what they last told us, and
    DEFAULT_TIMEZONE is the deployment's own.
    """
    for candidate in (*candidates, settings.DEFAULT_TIMEZONE):
        zone = _load(candidate)
        if zone is not None:
            return zone
    return UTC


def _load(name: Optional[str]):
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    if cleaned.upper() == "UTC":
        return UTC
    if ZoneInfo is None:
        logger.warning("zoneinfo is unavailable; falling back to UTC")
        return None
    try:
        return ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        # A client can send anything. An unknown zone is worth a log line, not a
        # failed scheduling request.
        logger.warning(f"Unknown timezone {cleaned!r}; ignoring it")
        return None


def now_in(tz) -> datetime:
    return datetime.now(UTC).astimezone(tz)


def to_local(value: datetime, tz) -> datetime:
    """Same instant, expressed in `tz`. A naive value is assumed to be UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz)


def local_wall_clock_to_utc(value: datetime, tz) -> datetime:
    """Read `value`'s date and time as a wall clock in `tz`, return the instant.

    Any offset already on `value` is discarded: the caller has decided that the
    fields are a local wall clock. `parse_model_datetime` is where that decision
    is made and explained.
    """
    naive = value.replace(tzinfo=None)
    return naive.replace(tzinfo=tz).astimezone(UTC)


def offset_label(tz, at: Optional[datetime] = None) -> str:
    """The zone's UTC offset at `at`, as "+03:00".

    Computed at a moment rather than taken from the zone, because half the world
    changes offset twice a year and the prompt hands this string to the model as
    a literal to copy.
    """
    reference = (at or datetime.now(UTC)).astimezone(tz)
    delta = reference.utcoffset() or timedelta(0)
    total_minutes = int(delta.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def zone_name(tz) -> str:
    """A display name for the prompt: "Asia/Jerusalem", or "UTC"."""
    return getattr(tz, "key", None) or str(tz)


def remember_timezone(db, user, requested: Optional[str]) -> Optional[str]:
    """Store a newly reported zone on the user, and return the name to use now.

    The browser reports its zone on every chat request, which is the only source
    that knows where the user actually is — and it changes when they travel. It
    is persisted so anything that runs without a request in hand (a background
    summary, a future digest) still has a wall clock to work in.

    An unusable value is ignored rather than stored, so a broken client cannot
    overwrite a good zone with junk. `user` is duck-typed to keep this module
    free of model imports.
    """
    candidate = (requested or "").strip()
    if candidate and _load(candidate) is not None:
        if getattr(user, "timezone", None) != candidate:
            user.timezone = candidate
            db.commit()
        return candidate
    return getattr(user, "timezone", None)
