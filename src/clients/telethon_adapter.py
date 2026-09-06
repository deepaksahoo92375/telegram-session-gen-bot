"""Telethon-based session generation adapter.

Owns exactly one TelegramClient per flow. Never logs api_hash, phone, code,
password, or the resulting session string/auth key.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import SQLiteSession, StringSession

from src.clients.errors import (
    CodeExpiredError,
    FloodWaitErrorNormalized,
    InvalidCodeError,
    InvalidCredentialsError,
    InvalidPasswordError,
    InvalidPhoneError,
    PasswordRequiredError,
)
from src.security.redaction import redact_exception

logger = logging.getLogger(__name__)


class TelethonAdapter:
    """Wraps a single Telethon client through the login lifecycle."""

    def __init__(self, api_id: int, api_hash: str, *, session_file_path: Optional[Path] = None) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_file_path = session_file_path
        session = SQLiteSession(str(session_file_path)) if session_file_path else StringSession()
        self.client = TelegramClient(session, api_id, api_hash)
        self._phone_code_hash: Optional[str] = None
        self._phone: Optional[str] = None

    async def connect(self) -> None:
        try:
            await self.client.connect()
        except Exception as exc:
            logger.error("Telethon connect failed: %s", redact_exception(exc))
            raise

    async def send_code(self, phone: str) -> None:
        self._phone = phone
        try:
            sent = await self.client.send_code_request(phone)
            self._phone_code_hash = sent.phone_code_hash
        except ApiIdInvalidError as exc:
            raise InvalidCredentialsError("Invalid API ID/hash.") from exc
        except PhoneNumberInvalidError as exc:
            raise InvalidPhoneError("Invalid phone number.") from exc
        except FloodWaitError as exc:
            raise FloodWaitErrorNormalized(exc.seconds) from exc
        except Exception as exc:
            logger.error("Telethon send_code failed: %s", redact_exception(exc))
            raise

    async def sign_in_with_code(self, code: str) -> None:
        if not self._phone or not self._phone_code_hash:
            raise InvalidCodeError("No pending code request.")
        try:
            await self.client.sign_in(
                phone=self._phone, code=code, phone_code_hash=self._phone_code_hash
            )
        except SessionPasswordNeededError as exc:
            raise PasswordRequiredError("2FA password required.") from exc
        except PhoneCodeInvalidError as exc:
            raise InvalidCodeError("Invalid code.") from exc
        except PhoneCodeExpiredError as exc:
            raise CodeExpiredError("Code expired.") from exc
        except FloodWaitError as exc:
            raise FloodWaitErrorNormalized(exc.seconds) from exc
        except Exception as exc:
            logger.error("Telethon sign_in failed: %s", redact_exception(exc))
            raise

    async def sign_in_with_password(self, password: str) -> None:
        try:
            await self.client.sign_in(password=password)
        except PasswordHashInvalidError as exc:
            raise InvalidPasswordError("Invalid password.") from exc
        except FloodWaitError as exc:
            raise FloodWaitErrorNormalized(exc.seconds) from exc
        except Exception as exc:
            logger.error("Telethon 2FA sign_in failed: %s", redact_exception(exc))
            raise

    async def disable_forwarding_hint(self) -> None:
        """Telethon has no client-side "disable forwarding" toggle for the
        generated session; forwarding restriction is applied at the bot-chat
        level (see PrivateChatMiddleware / protect_content on sent messages).
        """
        return None

    async def export_string_session(self) -> str:
        return self.client.session.save()  # type: ignore[return-value]

    async def export_session_file_bytes(self) -> bytes:
        if not self._session_file_path:
            raise RuntimeError("Adapter was not configured for file-based sessions.")
        # Ensure the session is flushed to disk before reading it back.
        self.client.session.save()
        return self._session_file_path.read_bytes()

    async def disconnect(self) -> None:
        try:
            await self.client.disconnect()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Telethon disconnect error: %s", redact_exception(exc))
