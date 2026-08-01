from collections import defaultdict, deque
from time import monotonic


class RateLimitExceeded(RuntimeError):
    """Raised when a caller exceeds one configured in-process pilot limit."""

    def __init__(self, retry_after_s: int):
        super().__init__("Rate limit exceeded.")
        self.retry_after_s = max(1, retry_after_s)


class InMemoryRateLimiter:
    """Sliding-window limiter for the supported single-process deployment."""

    def __init__(self) -> None:
        self._events: dict[str, deque[tuple[float, str | None]]] = defaultdict(deque)
        self._window_s: dict[str, int] = {}
        self._check_count = 0

    def _evict_inactive_keys(self, now: float) -> None:
        """Periodically discard user buckets whose windows have fully elapsed."""
        for existing_key, existing_events in list(self._events.items()):
            threshold = now - self._window_s.get(existing_key, 1)
            while existing_events and existing_events[0][0] <= threshold:
                existing_events.popleft()
            if not existing_events:
                self._events.pop(existing_key, None)
                self._window_s.pop(existing_key, None)

    def check(
        self,
        key: str,
        limit: int,
        window_s: int,
        event_id: str | None = None,
    ) -> None:
        if limit <= 0 or window_s <= 0:
            raise ValueError("Rate-limit size and window must be positive.")
        now = monotonic()
        self._check_count += 1
        if self._check_count % 1024 == 0:
            self._evict_inactive_keys(now)
        events = self._events[key]
        self._window_s[key] = window_s
        threshold = now - window_s
        while events and events[0][0] <= threshold:
            events.popleft()
        if event_id is not None and any(stored_id == event_id for _, stored_id in events):
            return
        if len(events) >= limit:
            retry_after = int(window_s - (now - events[0][0])) + 1
            raise RateLimitExceeded(retry_after)
        events.append((now, event_id))
