"""HTTP layer.

Routes only. Each handler reads the request, calls a service, and turns the
result into a status code. Nothing in here knows how news is fetched, how the
model is called, or how a row is stored.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session

from config import settings
from database import Analysis, create_db_and_tables, get_session
from dependencies import analyse_rate_limit, search_rate_limit
from models import Article
from observability import configure_logging, new_request_id, request_id_var
from services import analysis as analysis_service
from services.ai import AIProviderError
from services.news import NewsProviderError, search_news

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before yield) and once at shutdown (after)."""
    configure_logging()
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan, title="News AI")


# ---------------------------------------------------------------------------
# Cross-origin access
#
# The SPA is served from Vercel and this API from Render, so every browser call
# is cross-origin. Origins come from the environment, never hardcoded, so
# production and local development differ by configuration alone.
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request correlation
#
# Tag every request with an id, echo it back, and make it available to every
# log line produced while handling it. An id supplied by the caller is honoured
# so a trace can span the frontend and the API.
# ---------------------------------------------------------------------------


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or new_request_id()
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Health and readiness
# ---------------------------------------------------------------------------


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
        logger.warning("event=readiness.failed error=%s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Articles - live news search, proxied so the API key stays server side
# ---------------------------------------------------------------------------


@app.get(
    "/api/articles",
    response_model=list[Article],
    dependencies=[Depends(search_rate_limit)],
)
async def search_articles(q: str = Query(..., min_length=1)):
    try:
        return await search_news(q)
    except NewsProviderError as exc:
        # The service raised a domain error; deciding it means 502 is this layer's job.
        logger.warning("event=news.failed error=%s", exc)
        raise HTTPException(status_code=502, detail="News provider error") from exc


# ---------------------------------------------------------------------------
# Analyses - AI summary and sentiment, stored and read back
# ---------------------------------------------------------------------------


@app.post(
    "/api/analyses",
    response_model=Analysis,
    status_code=201,
    dependencies=[Depends(analyse_rate_limit)],
)
def create_analysis(
    payload: Article,
    response: Response,
    session: Session = Depends(get_session),
):
    """201 when a new analysis was created, 200 when an existing one was reused."""
    try:
        analysis, created = analysis_service.get_or_create_analysis(session, payload)
    except AIProviderError as exc:
        logger.warning("event=ai.failed error=%s", exc)
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
