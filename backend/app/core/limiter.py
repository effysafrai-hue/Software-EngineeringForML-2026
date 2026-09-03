from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.security import decode_jwt_token


def _user_id_from_request(request: Request) -> Optional[str]:
    """Read the caller's user id straight off the bearer token.

    The limiter runs before the route's dependencies, so `current_user` does not
    exist yet; the token has to be decoded here. An unreadable or absent token
    returns None and the caller falls back to the client address.
    """
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None

    payload = decode_jwt_token(token.strip())
    if not payload:
        return None

    subject = payload.get("sub")
    return str(subject) if subject else None


def user_or_ip_key(request: Request) -> str:
    """Rate-limit key: the authenticated user, or the client address when anonymous.

    Per-user is the meaningful unit for content spam. Anonymous requests still
    get a bucket so an unauthenticated flood is not simply unlimited.
    """
    user_id = _user_id_from_request(request)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=user_or_ip_key)


def reset_rate_limits() -> bool:
    """Drop every counter. Returns True if a storage backend was actually cleared.

    Tests call this between cases. With a per-user key the buckets outlive a
    single test, so without a reset the first test to post would spend the
    budget of every test after it. The return value lets a test assert the reset
    really happened instead of silently trusting a no-op — slowapi has moved the
    storage attribute around between releases, so all the known spellings are
    tried.
    """
    cleared = False

    reset_method = getattr(limiter, "reset", None)
    if callable(reset_method):
        try:
            reset_method()
            cleared = True
        except Exception:
            pass

    for owner, attr in ((limiter, "_storage"), (getattr(limiter, "limiter", None), "storage")):
        storage = getattr(owner, attr, None) if owner is not None else None
        if storage is not None and hasattr(storage, "reset"):
            try:
                storage.reset()
                cleared = True
            except Exception:
                pass

    return cleared
