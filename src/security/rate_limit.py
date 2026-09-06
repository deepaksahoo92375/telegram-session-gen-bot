"""Simple in-memory per-user sliding-window rate limiter.

No external dependencies (Redis, etc.) are used, matching the "no database"
requirement; state resets on process restart, which is acceptable for a
lightweight abuse-prevention control.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limiter: max ``max_events`` per ``window_seconds`` per key."""

    def __init__(self, max_events: int, window_seconds: int) -> None:
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def _prune(self, key: int, now: float) -> None:
        bucket = self._events[key]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def allow(self, key: int, *, now: float | None = None) -> bool:
        """Return True and record the event if ``key`` is under the limit."""
        now = time.monotonic() if now is None else now
        self._prune(key, now)
        bucket = self._events[key]
        if len(bucket) >= self.max_events:
            return False
        bucket.append(now)
        return True

    def remaining(self, key: int, *, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        self._prune(key, now)
        return max(0, self.max_events - len(self._events[key]))

    def reset(self, key: int) -> None:
        self._events.pop(key, None)
