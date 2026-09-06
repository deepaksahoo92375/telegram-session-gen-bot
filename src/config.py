"""Application configuration loaded strictly from environment variables.

No secrets are hard-coded. No secrets are logged. This module intentionally
avoids printing or logging the loaded BOT_TOKEN value.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_int(env_name: str, default: int) -> int:
    raw = os.getenv(env_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {env_name} must be an integer") from exc


def _parse_user_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        ids.add(int(chunk))
    return frozenset(ids)


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings."""

    bot_token: str
    allowed_user_ids: frozenset[int]
    rate_limit_max_starts: int
    rate_limit_window_seconds: int
    max_auth_attempts: int
    flow_timeout_seconds: int
    secure_tmp_dir: str
    log_level: str = field(default="INFO")

    @staticmethod
    def load() -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN environment variable is required. "
                "Obtain it from @BotFather on Telegram."
            )
        return Settings(
            bot_token=token,
            allowed_user_ids=_parse_user_ids(os.getenv("ALLOWED_USER_IDS")),
            rate_limit_max_starts=_parse_int("RATE_LIMIT_MAX_STARTS", 3),
            rate_limit_window_seconds=_parse_int("RATE_LIMIT_WINDOW_SECONDS", 600),
            max_auth_attempts=_parse_int("MAX_AUTH_ATTEMPTS", 3),
            flow_timeout_seconds=_parse_int("FLOW_TIMEOUT_SECONDS", 300),
            secure_tmp_dir=os.getenv("SECURE_TMP_DIR", "/tmp/tgsession_secure"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive redaction
        # Never allow accidental repr/log of the bot token.
        return "Settings(bot_token='***redacted***', ...)"
