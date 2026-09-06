"""Pyrogram-based session generation adapter.

Mirrors TelethonAdapter's interface so handlers stay client-agnostic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    FloodWait,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)

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


class PyrogramAdapter:
    """Wraps a single Pyrogram client through the login lifecycle."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        *,
        workdir: Optional[Path] = None,
        session_name: str = "session",
        in_memory: bool = True,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._workdir = workdir
        self._session_name = session_name
        self.client = Client(
            name=session_name,
            api_id=api_id,
            api_hash=api_hash,
            in_memory=in_memory,
            workdir=str(workdir) if workdir else ".",
            no_updates=True,
        )
        self._phone: Optional[str] = None
        self._phone_code_hash: Optional[str] = None

    async def connect(self) -> None:
        try:
            await self.client.connect()
        except Exception as exc:
            logger.error("Pyrogram connect failed: %s", redact_exception(exc))
            raise

    async def send_code(self, phone: str) -> None:
        self._phone = phone
        try:
            sent = await self.client.send_code(phone)
            self._phone_code_hash = sent.phone_code_hash
        except ApiIdInvalid as exc:
            raise InvalidCredentialsError("Invalid API ID/hash.") from exc
        except PhoneNumberInvalid as exc:
            raise InvalidPhoneError("Invalid phone number.") from exc
        except FloodWait as exc:
            raise FloodWaitErrorNormalized(exc.value) from exc
        except Exception as exc:
            logger.error("Pyrogram send_code failed: %s", redact_exception(exc))
            raise

    async def sign_in_with_code(self, code: str) -> None:
        if not self._phone or not self._phone_code_hash:
            raise InvalidCodeError("No pending code request.")
        try:
            await self.client.sign_in(
                phone_number=self._phone,
                phone_code_hash=self._phone_code_hash,
                phone_code=code,
            )
        except SessionPasswordNeeded as exc:
            raise PasswordRequiredError("2FA password required.") from exc
        except PhoneCodeInvalid as exc:
            raise InvalidCodeError("Invalid code.") from exc
        except PhoneCodeExpired as exc:
            raise CodeExpiredError("Code expired.") from exc
        except FloodWait as exc:
            raise FloodWaitErrorNormalized(exc.value) from exc
        except Exception as exc:
            logger.error("Pyrogram sign_in failed: %s", redact_exception(exc))
            raise

    async def sign_in_with_password(self, password: str) -> None:
        try:
            await self.client.check_password(password)
        except PasswordHashInvalid as exc:
            raise InvalidPasswordError("Invalid password.") from exc
        except FloodWait as exc:
            raise FloodWaitErrorNormalized(exc.value) from exc
        except Exception as exc:
            logger.error("Pyrogram 2FA check_password failed: %s", redact_exception(exc))
            raise

    async def export_string_session(self) -> str:
        return await self.client.export_session_string()

    async def export_session_file_bytes(self) -> bytes:
        if not self._workdir:
            raise RuntimeError("Adapter was not configured for file-based sessions.")
        await self.client.storage.save()
        path = Path(self._workdir) / f"{self._session_name}.session"
        return path.read_bytes()

    async def disconnect(self) -> None:
        try:
            await self.client.disconnect()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Pyrogram disconnect error: %s", redact_exception(exc))
