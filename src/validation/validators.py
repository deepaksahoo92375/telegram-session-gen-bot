"""Input validation for all user-supplied values.

Every validator raises ``ValidationError`` with a user-safe message (never
echoing back exactly what was entered for the sensitive fields) or returns a
normalized value.
"""
from __future__ import annotations

import re


class ValidationError(Exception):
    """Raised when user input fails validation."""


_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_API_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$")
_CODE_CLEAN_RE = re.compile(r"[\s\-_.]")


def validate_api_id(raw: str) -> int:
    raw = raw.strip()
    if not raw.isdigit():
        raise ValidationError("API ID must be a positive number. Please try again.")
    value = int(raw)
    if not (1 <= value <= 2_147_483_647):
        raise ValidationError("API ID is out of range. Please check my.telegram.org and try again.")
    return value


def validate_api_hash(raw: str) -> str:
    raw = raw.strip()
    if not _API_HASH_RE.match(raw):
        raise ValidationError("API Hash must be exactly 32 hex characters. Please try again.")
    return raw.lower()


def validate_phone(raw: str) -> str:
    raw = raw.strip().replace(" ", "")
    if not _PHONE_RE.match(raw):
        raise ValidationError(
            "Please send a valid phone number in international format, e.g. +15551234567."
        )
    return raw


def validate_code(raw: str) -> str:
    """Accept digits possibly separated by spaces/dashes (to avoid Telegram's
    login-code auto-detection warnings when typed as a plain message)."""
    cleaned = _CODE_CLEAN_RE.sub("", raw.strip())
    if not cleaned.isdigit() or not (4 <= len(cleaned) <= 6):
        raise ValidationError("The code must be 4-6 digits. Please try again.")
    return cleaned


def validate_password(raw: str) -> str:
    if len(raw) == 0:
        raise ValidationError("Password cannot be empty. Please try again.")
    if len(raw) > 512:
        raise ValidationError("That doesn't look like a valid password. Please try again.")
    return raw


def validate_client_choice(raw: str) -> str:
    value = raw.strip().lower()
    if value not in ("telethon", "pyrogram"):
        raise ValidationError("Please choose Telethon or Pyrogram using the buttons.")
    return value


def validate_output_choice(raw: str) -> str:
    value = raw.strip().lower()
    if value not in ("string", "file"):
        raise ValidationError("Please choose String or File using the buttons.")
    return value
