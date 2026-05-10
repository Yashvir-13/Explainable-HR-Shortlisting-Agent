from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)")
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"system prompt",
    r"developer message",
    r"reveal (the )?(secret|api key|prompt)",
    r"act as",
    r"you are now",
]


def mask_pii(text: str) -> str:
    masked = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return PHONE_RE.sub("[PHONE_REDACTED]", masked)


def sanitize_input(text: str, limit: int = 25000) -> str:
    clean = text.replace("\x00", " ")
    for pattern in INJECTION_PATTERNS:
        clean = re.sub(pattern, "[POTENTIAL_PROMPT_INJECTION_REMOVED]", clean, flags=re.I)
    return clean[:limit]

