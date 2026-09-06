"""Ephemeral, in-memory-only data structures for an active flow.

Instances of FlowContext are never serialized, never written to a database,
and are wiped via security.cleanup.full_cleanup() at the end of every flow.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class FlowContext:
    """Holds all ephemeral state for one user's in-progress flow."""

    user_id: int
    chat_id: int
    client_type: str = ""  # "telethon" | "pyrogram"
    output_type: str = ""  # "string" | "file"
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    phone: Optional[str] = None
    adapter: Optional[Any] = None  # TelethonAdapter | PyrogramAdapter
    temp_dir: Optional[Path] = None
    temp_files: list[Path] = field(default_factory=list)
    auth_attempts: int = 0
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def is_expired(self, timeout_seconds: int) -> bool:
        return (time.monotonic() - self.last_activity) > timeout_seconds

    def as_wipeable_dict(self) -> dict:
        """A dict view used purely so cleanup.wipe_dict() can null references."""
        return self.__dict__
