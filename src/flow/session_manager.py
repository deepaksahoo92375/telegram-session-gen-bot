"""Central manager enforcing "one active flow per user" + TTL expiration.

This is the single source of truth for active FlowContext objects. It never
persists anything to disk or a database; state lives only in process memory
for the lifetime of a flow.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from src.flow.models import FlowContext
from src.security.cleanup import full_cleanup
from src.security.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

ExpiryCallback = Callable[[int, FlowContext], Awaitable[None]]


class SessionManager:
    """Owns all active FlowContext instances and their lifecycle."""

    def __init__(
        self,
        *,
        flow_timeout_seconds: int,
        rate_limiter: RateLimiter,
        reap_interval_seconds: int = 15,
    ) -> None:
        self._flows: dict[int, FlowContext] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._flow_timeout_seconds = flow_timeout_seconds
        self._rate_limiter = rate_limiter
        self._reap_interval_seconds = reap_interval_seconds
        self._on_expire: Optional[ExpiryCallback] = None
        self._reaper_task: Optional[asyncio.Task] = None

    def set_expiry_callback(self, callback: ExpiryCallback) -> None:
        self._on_expire = callback

    def _lock_for(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    def has_active_flow(self, user_id: int) -> bool:
        return user_id in self._flows

    def get_flow(self, user_id: int) -> Optional[FlowContext]:
        flow = self._flows.get(user_id)
        if flow:
            flow.touch()
        return flow

    def try_start_flow(self, user_id: int, chat_id: int) -> tuple[bool, str]:
        """Attempt to start a new flow.

        Returns (success, reason_if_failed).
        """
        if user_id in self._flows:
            return False, "already_active"
        if not self._rate_limiter.allow(user_id):
            return False, "rate_limited"
        self._flows[user_id] = FlowContext(user_id=user_id, chat_id=chat_id)
        return True, ""

    async def end_flow(self, user_id: int) -> None:
        """Clean up and remove a flow, whatever its outcome."""
        async with self._lock_for(user_id):
            flow = self._flows.pop(user_id, None)
            if flow is None:
                return
            await full_cleanup(
                client=getattr(flow.adapter, "client", None),
                temp_files=flow.temp_files,
                state_data=flow.as_wipeable_dict(),
            )

    async def start_reaper(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._reap_loop())

    async def stop_reaper(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None

    async def _reap_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._reap_interval_seconds)
                await self.reap_expired()
        except asyncio.CancelledError:
            raise

    async def reap_expired(self) -> list[int]:
        """Expire and wipe any flow that has been inactive too long."""
        expired_users = [
            uid for uid, flow in self._flows.items()
            if flow.is_expired(self._flow_timeout_seconds)
        ]
        for uid in expired_users:
            flow = self._flows.get(uid)
            if flow is None:
                continue
            if self._on_expire is not None:
                try:
                    await self._on_expire(uid, flow)
                except Exception:  # pragma: no cover - notification best-effort
                    logger.warning("Expiry notification failed for a user")
            await self.end_flow(uid)
        return expired_users

    async def shutdown_all(self) -> None:
        """Cleanup every active flow, e.g. on process shutdown."""
        for uid in list(self._flows.keys()):
            await self.end_flow(uid)
