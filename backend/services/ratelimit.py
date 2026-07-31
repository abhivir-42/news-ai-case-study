import time


class SlidingWindowLimiter:
    """Counts requests per key over a rolling window.

    In-process and per-instance: two Render instances would each allow the full
    limit, and the counters reset on deploy. Keys are also never evicted once a
    client has been seen. Production uses a shared store with TTLs (Redis) so the
    limit is global and the memory is bounded, but the shape of the check is the same.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> float | None:
        """Record a hit. Returns None if allowed, or seconds until the window frees."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        hits = [hit for hit in self._hits.get(key, []) if hit > cutoff]

        if len(hits) >= self.limit:
            self._hits[key] = hits
            return self.window_seconds - (now - hits[0])

        hits.append(now)
        self._hits[key] = hits
        return None
