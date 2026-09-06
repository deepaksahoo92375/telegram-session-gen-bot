"""Application entrypoint: wires config, middleware, handlers, and the
SessionManager, and guarantees cleanup on shutdown."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import Settings
from src.constants import TIMEOUT_TEXT
from src.flow.models import FlowContext
from src.flow.session_manager import SessionManager
from src.handlers import cancel, flow_handlers, start
from src.middlewares.private_chat import PrivateChatOnlyMiddleware
from src.security.redaction import install_redacting_logging
from src.security.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


async def _notify_expired(bot: Bot):
    async def _inner(user_id: int, flow: FlowContext) -> None:
        try:
            await bot.send_message(flow.chat_id, TIMEOUT_TEXT)
        except Exception:  # pragma: no cover - best effort notification
            pass
    return _inner


async def main() -> None:
    settings = Settings.load()
    install_redacting_logging(settings.log_level)
    logger.info("Starting session-generator bot")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    rate_limiter = RateLimiter(
        max_events=settings.rate_limit_max_starts,
        window_seconds=settings.rate_limit_window_seconds,
    )
    manager = SessionManager(
        flow_timeout_seconds=settings.flow_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    manager.set_expiry_callback(await _notify_expired(bot))

    dp["manager"] = manager
    dp["settings"] = settings

    private_only = PrivateChatOnlyMiddleware(settings.allowed_user_ids)
    dp.message.middleware(private_only)
    dp.callback_query.middleware(private_only)

    dp.include_router(start.router)
    dp.include_router(flow_handlers.router)
    dp.include_router(cancel.router)

    await manager.start_reaper()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down — wiping all active sessions")
        await manager.stop_reaper()
        await manager.shutdown_all()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
