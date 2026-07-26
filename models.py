from pydantic import BaseModel


class Article(BaseModel):
    title: str
    description: str | None = None
    content: str | None = None
    url: str
    image: str | None = None
    published_at: str
    source_name: str
