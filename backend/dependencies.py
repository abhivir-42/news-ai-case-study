"""HTTP-layer dependencies.

Rate limiting lives here rather than in services/ because deciding that a
client has gone over budget is a transport concern: it reads request headers
and returns 429. The counting algorithm itself is in services/ratelimit.py and
knows nothing about HTTP.
"""

from fastapi import HTTPException, Request

from config import settings
from services.ratelimit import SlidingWindowLimiter

# POST /api/analyses spends OpenAI money; GET /api/articles spends GNews quota.
analyse_limiter = SlidingWindowLimiter(settings.analyse_rate_limit_per_hour, 3600)
search_limiter = SlidingWindowLimiter(settings.search_rate_limit_per_minute, 60)


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting purposes."""
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client. Only trustworthy because the
            # only route to this app is through Render's proxy, which sets it.
            # If anything can reach the app directly, this header is spoofable.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(limiter: SlidingWindowLimiter, request: Request) -> None:
    retry_after = limiter.check(client_key(request))
    if retry_after is None:
        return
    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded",
        # Tell the client when to come back rather than making it guess.
        headers={"Retry-After": str(int(retry_after) + 1)},
    )


def analyse_rate_limit(request: Request) -> None:
    _enforce(analyse_limiter, request)


def search_rate_limit(request: Request) -> None:
    _enforce(search_limiter, request)
