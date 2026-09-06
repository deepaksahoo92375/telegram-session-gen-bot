"""Best-effort in-memory and on-disk cleanup of everything sensitive.

Python strings are immutable, so we cannot guarantee overwriting string
contents in memory; this module clears references so objects become
eligible for garbage collection immediately, disconnects live clients, and
wipes any temp files associated with a flow. This is defense-in-depth
alongside never persisting secrets and minimizing their lifetime.
"""
from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any

from src.security.redaction import redact_exception
from src.security.secure_files import shred_file

logger = logging.getLogger(__name__)


async def disconnect_client(client: Any) -> None:
    """Disconnect a Telethon or Pyrogram client instance, swallowing errors."""
    if client is None:
        return
    try:
        disconnect = getattr(client, "disconnect", None)
        if disconnect is not None:
            result = disconnect()
            if hasattr(result, "__await__"):
                await result
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Error disconnecting client: %s", redact_exception(exc))


def wipe_temp_files(paths: list[Path]) -> None:
    """Securely shred and delete every temp file path given."""
    for path in paths:
        shred_file(path)


def wipe_dict(data: dict) -> None:
    """Clear a dictionary's values in place (best effort) then clear it."""
    for key in list(data.keys()):
        data[key] = None
    data.clear()


async def full_cleanup(
    *,
    client: Any = None,
    temp_files: list[Path] | None = None,
    state_data: dict | None = None,
    fsm_context: Any = None,
) -> None:
    """Run the complete cleanup sequence for a flow.

    Safe to call multiple times and safe to call with partially-initialized
    state (e.g. cancellation before a client was ever created).
    """
    await disconnect_client(client)
    if temp_files:
        wipe_temp_files(temp_files)
    if state_data is not None:
        wipe_dict(state_data)
    if fsm_context is not None:
        try:
            await fsm_context.clear()
        except Exception as exc:  # pragma: no cover
            logger.warning("Error clearing FSM context: %s", redact_exception(exc))
    gc.collect()
