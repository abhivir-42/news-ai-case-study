from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends, Response
from pydantic import BaseModel
from sqlmodel import Session, select


from config import settings
from database import Analysis, get_session, create_db_and_tables
from ai import analyse_article

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


class Article(BaseModel):
    title: str
    description: str | None = None
    content: str | None = None
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
            content=a.get("content"),
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


@app.post("/api/analyses", response_model=Analysis, status_code=201)
def create_analysis(
    payload: Article,
    response: Response,
    session: Session = Depends(get_session),
):
    # 1. Dedup: has this URL already been analyzed?
    existing = session.exec(select(Analysis).where(Analysis.url == payload.url)).first()
    if existing:
        response.status_code = 200  # already existed — not "created"
        return existing

    # 2. Analyze with OpenAI
    result = analyse_article(payload.title, payload.description, payload.content)

    # 3. Store the result
    analysis = Analysis(
        url=payload.url,
        title=payload.title,
        source=payload.source_name,
        published_at=payload.published_at,
        summary=result.summary,
        sentiment=result.sentiment.value,
        sentiment_score=result.sentiment_score,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    response.status_code = 201  # newly created
    return analysis
