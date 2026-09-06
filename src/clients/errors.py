"""Normalized, library-agnostic error types surfaced to handlers.

Handlers only need to catch these, keeping Telethon/Pyrogram-specific
exception types confined to the adapters.
"""
from __future__ import annotations


class ClientAdapterError(Exception):
    """Base class for all adapter-raised errors."""


class InvalidCredentialsError(ClientAdapterError):
    """API ID / API hash rejected by Telegram."""


class InvalidPhoneError(ClientAdapterError):
    """Phone number rejected by Telegram."""


class InvalidCodeError(ClientAdapterError):
    """Login code was wrong."""


class CodeExpiredError(ClientAdapterError):
    """Login code expired."""


class PasswordRequiredError(ClientAdapterError):
    """Two-step verification password is required."""


class InvalidPasswordError(ClientAdapterError):
    """Two-step verification password was wrong."""


class FloodWaitErrorNormalized(ClientAdapterError):
    """Telegram asked us to wait before retrying."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        super().__init__(f"Please wait {seconds}s before retrying (Telegram rate limit).")


class AuthorizationRevokedError(ClientAdapterError):
    """Session/authorization was revoked mid-flow."""
