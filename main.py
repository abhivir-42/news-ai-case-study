from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from config import settings
from database import create_db_and_tables

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

class Article(BaseModel):
    title: str
    description: str | None = None
    url: str
    image: str | None = None
    published_at: str
    source_name: str


@app.get("/api/articles", response_model=list[Article])
async def search_articles(q: str = Query(..., min_length=1)):
    params = {
        "q": q,
        "lang": "en",
        "max": 10,
        "apikey": settings.gnews_api_key,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GNEWS_SEARCH_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="News provider error")

    data = response.json()
    return [
        Article(
            title=a["title"],
            description=a.get("description"),
            url=a["url"],
            image=a.get("image"),
            published_at=a["publishedAt"],
            source_name=a["source"]["name"],
        )
        for a in data.get("articles", [])
    ]


@app.get("/health")
def health():
    return {"status": "ok"}

