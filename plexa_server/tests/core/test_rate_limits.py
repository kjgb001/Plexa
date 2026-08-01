import pytest

from plexa_server.core import rate_limits
from plexa_server.core.rate_limits import InMemoryRateLimiter, RateLimitExceeded


def test_rate_limit_retry_with_same_event_id_is_idempotent():
    limiter = InMemoryRateLimiter()

    limiter.check("message:user-1", limit=1, window_s=60, event_id="message-1")
    limiter.check("message:user-1", limit=1, window_s=60, event_id="message-1")

    with pytest.raises(RateLimitExceeded):
        limiter.check("message:user-1", limit=1, window_s=60, event_id="message-2")


def test_rate_limit_without_event_id_counts_each_attempt():
    limiter = InMemoryRateLimiter()

    limiter.check("session-create:user-1", limit=1, window_s=60)

    with pytest.raises(RateLimitExceeded):
        limiter.check("session-create:user-1", limit=1, window_s=60)


def test_rate_limiter_evicts_inactive_user_buckets(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(rate_limits, "monotonic", lambda: now[0])
    limiter = InMemoryRateLimiter()
    limiter.check("message:inactive", limit=1, window_s=60)

    now[0] = 61.0
    for index in range(1023):
        limiter.check("message:active", limit=2000, window_s=60, event_id=str(index))

    assert "message:inactive" not in limiter._events


def test_rate_limiter_rejects_invalid_limits():
    limiter = InMemoryRateLimiter()

    with pytest.raises(ValueError):
        limiter.check("message:user-1", limit=0, window_s=60)
