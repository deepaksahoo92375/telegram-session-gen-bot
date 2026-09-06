"""Middleware enforcing private-chat-only usage and an optional allow-list."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.constants import NOT_ALLOWED_TEXT, PRIVATE_ONLY_TEXT


class PrivateChatOnlyMiddleware(BaseMiddleware):
    """Rejects any update that isn't a private 1:1 chat, and enforces the
    optional ALLOWED_USER_IDS allow-list."""

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed_user_ids = allowed_user_ids
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = None
        user = None
        if isinstance(event, Update):
            if event.message:
                chat, user = event.message.chat, event.message.from_user
            elif event.callback_query and event.callback_query.message:
                chat, user = event.callback_query.message.chat, event.callback_query.from_user

        if chat is not None and chat.type != "private":
            # Silently ignore in groups to avoid leaking bot presence/behavior;
            # optionally reply once could be added, but we stay silent by design.
            return None

        if user is not None and self._allowed_user_ids and user.id not in self._allowed_user_ids:
            bot = data.get("bot")
            if bot is not None and chat is not None:
                await bot.send_message(chat.id, NOT_ALLOWED_TEXT)
            return None

        return await handler(event, data)
