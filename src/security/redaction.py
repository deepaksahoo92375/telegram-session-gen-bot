"""Utilities to keep sensitive values out of logs and exception messages.

Nothing in this module ever writes sensitive values to disk or to a logger;
its sole purpose is to strip/replace such values wherever they might
otherwise leak (log records, exception text, repr()).
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

_PLACEHOLDER = "[REDACTED]"

# Patterns that indicate a value which must never be logged verbatim.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{7,15}\b"),  # phone numbers / api_id-like long digit runs
    re.compile(r"\b[a-fA-F0-9]{32}\b"),  # api_hash-like 32 hex chars
    re.compile(r"\b\d{5,6}\b"),  # login codes
    re.compile(r"\b[A-Za-z0-9_-]{50,}\b"),  # session strings / auth keys (long tokens)
)

_SENSITIVE_KEYS = {
    "api_id",
    "api_hash",
    "phone",
    "phone_number",
    "code",
    "phone_code",
    "password",
    "session_string",
    "session",
    "auth_key",
    "token",
    "bot_token",
}


def redact_text(text: str) -> str:
    """Replace substrings that look like secrets with a placeholder.

    This is a best-effort heuristic filter used as a safety net around
    logging and exception formatting -- it is not a substitute for simply
    never logging sensitive values in the first place.
    """
    redacted = text
    for pattern in _PATTERNS:
        redacted = pattern.sub(_PLACEHOLDER, redacted)
    return redacted


def redact_mapping(data: dict) -> dict:
    """Return a shallow copy of ``data`` with sensitive keys redacted."""
    out = {}
    for key, value in data.items():
        if key.lower() in _SENSITIVE_KEYS:
            out[key] = _PLACEHOLDER
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


def redact_exception(exc: BaseException) -> str:
    """Return a redacted, safe-to-log string representation of an exception."""
    return f"{type(exc).__name__}: {redact_text(str(exc))}"


class RedactingFilter(logging.Filter):
    """A logging filter that redacts sensitive substrings from every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(str(record.getMessage()))
            record.args = ()
        except Exception:  # pragma: no cover - never let logging crash the app
            record.msg = _PLACEHOLDER
            record.args = ()
        return True


def install_redacting_logging(level: str = "INFO", extra_loggers: Iterable[str] = ()) -> None:
    """Install the redacting filter on the root logger and named loggers.

    Also raises third-party libraries' log levels so verbose/debug logs
    from Telethon/Pyrogram (which can include protocol details) are
    suppressed by default.
    """
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.handlers = [handler]

    for name in ("telethon", "pyrogram", *extra_loggers):
        logging.getLogger(name).setLevel(max(logging.WARNING, logging.getLevelName(level)
                                              if isinstance(level, int) else logging.WARNING))
        logging.getLogger(name).addFilter(RedactingFilter())
