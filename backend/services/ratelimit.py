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

    def check(self, key: str, cost: int = 1) -> float | None:
        """Record `cost` hits. Returns None if allowed, or seconds until the window frees.

        `cost` exists because one request is not always one unit of spend: a bulk
        analyse makes a model call per article, so it has to pay for each one or it
        becomes a cheaper route to the same bill.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        hits = [hit for hit in self._hits.get(key, []) if hit > cutoff]

        if len(hits) + cost > self.limit:
            self._hits[key] = hits
            # No hits yet means the request is priced above the limit itself, so
            # waiting cannot help. Report the full window rather than index into [].
            oldest = hits[0] if hits else now
            return self.window_seconds - (now - oldest)

        hits.extend([now] * cost)
        self._hits[key] = hits
        return None
