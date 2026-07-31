import httpx
from pydantic import ValidationError

from config import settings
from models import Article

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"


class NewsProviderError(Exception):
    """Raised when the upstream news provider fails."""


async def search_news(query: str, max_results: int = 10) -> list[Article]:
    params = {
        "q": query,
        "lang": "en",
        "max": max_results,
        "apikey": settings.gnews_api_key.get_secret_value(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(GNEWS_SEARCH_URL, params=params)
    except httpx.HTTPError as exc:
        raise NewsProviderError(f"GNews request failed: {exc}") from exc

    if response.status_code != 200:
        raise NewsProviderError(f"GNews returned {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise NewsProviderError("GNews returned a body that is not JSON") from exc

    # A 200 is not proof of success: an error body has no articles list.
    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        raise NewsProviderError("GNews response contained no articles list")

    return [_to_article(a) for a in articles]


def _to_article(raw: dict) -> Article:
    """Map one GNews item onto our own shape.

    This is the boundary that stops the provider's shape leaking inward, so it has to
    distrust the payload rather than assume it. Anything unexpected becomes a
    NewsProviderError, which the route already knows how to turn into a 502.
    """
    try:
        return Article(
            title=raw["title"],
            description=raw.get("description"),
            content=raw.get("content"),
            url=raw["url"],
            image=raw.get("image"),
            published_at=raw["publishedAt"],
            source_name=raw["source"]["name"],
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise NewsProviderError(f"malformed article in GNews response: {exc}") from exc
