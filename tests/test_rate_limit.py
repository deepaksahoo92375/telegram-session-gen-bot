from src.security.rate_limit import RateLimiter


def test_allows_up_to_max_events():
    limiter = RateLimiter(max_events=2, window_seconds=60)
    assert limiter.allow(1, now=0.0) is True
    assert limiter.allow(1, now=1.0) is True
    assert limiter.allow(1, now=2.0) is False  # exceeds limit within window


def test_window_expiry_allows_again():
    limiter = RateLimiter(max_events=1, window_seconds=10)
    assert limiter.allow(1, now=0.0) is True
    assert limiter.allow(1, now=5.0) is False
    assert limiter.allow(1, now=11.0) is True  # window has slid past


def test_independent_per_key():
    limiter = RateLimiter(max_events=1, window_seconds=10)
    assert limiter.allow(1, now=0.0) is True
    assert limiter.allow(2, now=0.0) is True  # different user, independent bucket


def test_reset_clears_bucket():
    limiter = RateLimiter(max_events=1, window_seconds=10)
    limiter.allow(1, now=0.0)
    limiter.reset(1)
    assert limiter.allow(1, now=0.5) is True
