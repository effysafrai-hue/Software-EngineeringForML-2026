"""Input hardening for user-authored forum content.

Forum bodies are plain text, so the policy is "no markup at all" rather than an
allow-list of safe tags: anything a browser would parse as a tag is removed. That
is simpler to reason about than a whitelist, and it cannot be defeated by an
attribute-level payload (`<img onerror=...>`) the way a naive tag filter can.
What counts as a tag follows the browser rule — "<" immediately followed by a
letter or a slash — so a "<" used as a comparison in prose is left alone.

If rich text is ever wanted, swap these helpers for `bleach.clean` with an
explicit allow-list rather than loosening the regexes below.
"""

import re
from typing import List, Optional

from fastapi import HTTPException, status

MAX_BODY_LENGTH = 20_000
MAX_MEDIA_ITEMS = 10

# Elements whose *content* is dangerous too, so the whole block goes rather than
# just its tags: stripping only the tags from "<script>alert(1)</script>" would
# leave the payload behind as visible text ready to be re-injected elsewhere.
_RAW_TEXT_ELEMENTS = "script|style|iframe|object|embed|svg|math|template|noscript"

# A browser only starts a tag when "<" is followed immediately by a letter or a
# slash, and these patterns match that rule deliberately. A looser "<[^>]*>"
# would eat straight through ordinary prose — "is a < b the same as b > a?"
# reads as a tag to it, and the sentence loses its middle.
_RAW_TEXT_BLOCK_RE = re.compile(
    rf"<({_RAW_TEXT_ELEMENTS})\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_UNCLOSED_RAW_TEXT_RE = re.compile(rf"</?({_RAW_TEXT_ELEMENTS})\b[^>]*>?", re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_ANY_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")

# Only neutralise a scheme that is actually acting as one: requiring a non-space
# character straight after the colon keeps ordinary prose ("JavaScript: The Good
# Parts") intact while still defusing "javascript:alert(1)".
_DANGEROUS_SCHEME_RE = re.compile(r"\b(?:javascript|vbscript):(?=\S)", re.IGNORECASE)
_DANGEROUS_DATA_RE = re.compile(r"\bdata:(?=text/html|application/)", re.IGNORECASE)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{4,}")

# A media reference must be a path this server itself minted in /uploads. Anything
# else — an absolute URL, a protocol-relative "//evil.tld/x.png", a traversal
# attempt — is refused, so media_urls can never become an injection point for the
# client that renders it.
_UPLOAD_PATH_RE = re.compile(r"^/uploads/[A-Za-z0-9][A-Za-z0-9_-]*\.[A-Za-z0-9]{1,5}$")


def sanitize_user_text(raw: Optional[str], *, field: str = "body") -> str:
    """Strip markup and control characters from a user-supplied body.

    Raises 400 when nothing survives: a body that was only markup is a rejected
    submission, not an empty post.
    """
    text = raw or ""

    text = _CONTROL_CHARS_RE.sub("", text)
    text = _COMMENT_RE.sub(" ", text)
    text = _RAW_TEXT_BLOCK_RE.sub(" ", text)
    text = _UNCLOSED_RAW_TEXT_RE.sub(" ", text)
    text = _ANY_TAG_RE.sub("", text)
    # An unterminated "<img src=x onerror=..." is deliberately left as literal
    # text: it can never form an element, and a rule broad enough to catch it
    # also swallows legitimate prose that happens to contain a "<".

    text = _DANGEROUS_SCHEME_RE.sub("[blocked]", text)
    text = _DANGEROUS_DATA_RE.sub("[blocked]", text)

    text = _EXCESS_BLANK_LINES_RE.sub("\n\n\n", text).strip()

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {field} is empty after removing markup.",
        )
    if len(text) > MAX_BODY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {field} exceeds the maximum length of {MAX_BODY_LENGTH} characters.",
        )
    return text


def validate_media_urls(urls: Optional[List[str]]) -> List[str]:
    """Accept only paths produced by this server's own upload endpoint."""
    items = urls or []
    if len(items) > MAX_MEDIA_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_MEDIA_ITEMS} media attachments are allowed.",
        )

    cleaned: List[str] = []
    for url in items:
        candidate = (url or "").strip()
        if not _UPLOAD_PATH_RE.match(candidate):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid media reference {candidate!r}. "
                    "Upload the file to /uploads first and send the path it returns."
                ),
            )
        cleaned.append(candidate)
    return cleaned
