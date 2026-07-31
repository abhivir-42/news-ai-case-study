"""API schemas: the shapes this service speaks over HTTP.

`Article` is the one article shape. services/news.py produces it from GNews,
POST /api/analyses accepts it as a body, and GET /api/articles returns it. Kept
in its own module so services and routes can both import it without a cycle.
"""

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    description: str | None = None
    content: str | None = None
    url: str
    image: str | None = None
    published_at: str
    source_name: str
