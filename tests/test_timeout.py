import pytest

from src.flow.session_manager import SessionManager
from src.security.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_flow_not_expired_before_timeout():
    manager = SessionManager(
        flow_timeout_seconds=100, rate_limiter=RateLimiter(5, 60)
    )
    ok, _ = manager.try_start_flow(user_id=1, chat_id=1)
    assert ok
    expired = await manager.reap_expired()
    assert expired == []
    assert manager.has_active_flow(1)


@pytest.mark.asyncio
async def test_flow_expires_and_is_wiped_after_timeout():
    manager = SessionManager(flow_timeout_seconds=0, rate_limiter=RateLimiter(5, 60))
    ok, _ = manager.try_start_flow(user_id=1, chat_id=1)
    assert ok
    flow = manager.get_flow(1)
    flow.last_activity -= 1  # force it into the past relative to timeout=0

    expired = await manager.reap_expired()
    assert expired == [1]
    assert not manager.has_active_flow(1)


@pytest.mark.asyncio
async def test_one_flow_per_user_enforced():
    manager = SessionManager(flow_timeout_seconds=100, rate_limiter=RateLimiter(5, 60))
    ok1, _ = manager.try_start_flow(user_id=1, chat_id=1)
    ok2, reason2 = manager.try_start_flow(user_id=1, chat_id=1)
    assert ok1 is True
    assert ok2 is False
    assert reason2 == "already_active"


@pytest.mark.asyncio
async def test_shutdown_all_clears_every_flow():
    manager = SessionManager(flow_timeout_seconds=100, rate_limiter=RateLimiter(5, 60))
    manager.try_start_flow(user_id=1, chat_id=1)
    manager.try_start_flow(user_id=2, chat_id=2)
    await manager.shutdown_all()
    assert not manager.has_active_flow(1)
    assert not manager.has_active_flow(2)
