"""API schemas: the shapes this service speaks over HTTP.

`Article` is the one article shape. services/news.py produces it from GNews,
POST /api/analyses accepts it as a body, and GET /api/articles returns it. Kept
in its own module so services and routes can both import it without a cycle.
"""

from typing import Literal

from pydantic import BaseModel

from database import Analysis


class Article(BaseModel):
    title: str
    description: str | None = None
    content: str | None = None
    url: str
    image: str | None = None
    published_at: str
    source_name: str


class AnalysisOutcome(BaseModel):
    """What happened to one article inside a bulk request.

    A single analyse can say "created" or "reused" with a status code, but ten of
    them in one request cannot. Each article carries its own verdict instead, so a
    caller can tell a fresh analysis from a cached one and a failure from either.
    """

    url: str
    status: Literal["created", "reused", "failed"]
    analysis: Analysis | None = None
    error: str | None = None
