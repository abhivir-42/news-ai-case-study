import httpx

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
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GNEWS_SEARCH_URL, params=params)

    if response.status_code != 200:
        raise NewsProviderError(f"GNews returned {response.status_code}")

    return [_to_article(a) for a in response.json().get("articles", [])]


def _to_article(raw: dict) -> Article:
    return Article(
        title=raw["title"],
        description=raw.get("description"),
        content=raw.get("content"),
        url=raw["url"],
        image=raw.get("image"),
        published_at=raw["publishedAt"],
        source_name=raw["source"]["name"],
    )
