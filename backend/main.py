from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from sqlalchemy import text
from sqlmodel import Session
from fastapi.middleware.cors import CORSMiddleware

from database import Analysis, create_db_and_tables, get_session
from models import Article
from services import analysis as analysis_service
from services.ai import AIProviderError
from services.news import NewsProviderError, search_news
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan, title="News AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness: is the process up? Deliberately touches nothing."""
    return {"status": "ok"}


@app.get("/ready")
def ready(session: Session = Depends(get_session)):
    """Readiness: can this instance actually serve traffic?

    Separate from /health on purpose. A liveness probe that queries the database
    restarts the app when the database blips, which fixes nothing. A readiness
    probe that does not query it reports healthy while every request fails.
    """
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.get("/api/articles", response_model=list[Article])
async def search_articles(q: str = Query(..., min_length=1)):
    try:
        return await search_news(q)
    except NewsProviderError as exc:
        raise HTTPException(status_code=502, detail="News provider error") from exc


@app.post("/api/analyses", response_model=Analysis, status_code=201)
def create_analysis(
    payload: Article,
    response: Response,
    session: Session = Depends(get_session),
):
    try:
        analysis, created = analysis_service.get_or_create_analysis(session, payload)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail="AI provider error") from exc
    if not created:
        response.status_code = 200
    return analysis


@app.get("/api/analyses", response_model=list[Analysis])
def list_analyses(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return analysis_service.list_analyses(session, limit)


@app.get("/api/analyses/{analysis_id}", response_model=Analysis)
def get_analysis(
    analysis_id: int,
    session: Session = Depends(get_session),
):
    analysis = analysis_service.get_analysis(session, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
