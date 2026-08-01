"""
Shared pytest fixtures for API tests.

These do not assert anything themselves. They give each test:
- an isolated in-memory DB (`session`)
- a FastAPI TestClient wired to that DB (`client`)
- an optional stub for the LLM (`fake_ai`)
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import dependencies
from database import get_session
from main import app
from services.ai import ArticleAnalysis, Sentiment


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Clear the limiters before every test.

    They are module-level singletons, so their counters outlive the test that
    filled them. Without this a test passes or fails on how many requests the
    tests that happened to run before it made.
    """
    dependencies.analyse_limiter._hits.clear()
    dependencies.search_limiter._hits.clear()


@pytest.fixture(name="session")
def session_fixture():
    """Fresh in-memory SQLite session for one test.

    StaticPool + check_same_thread=False keep a single shared connection so
    TestClient requests all see the same DB.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """HTTP client against the app, with get_session overridden to the test DB."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="fake_ai")
def fake_ai_fixture(monkeypatch):
    """Replace analyse_article so analysis tests don't call the real AI provider.

    Patch the import site in services.analysis (not services.ai).
    """
    def fake_analyse_article(title, description, content):
        return ArticleAnalysis(
            summary="Fake summary.",
            sentiment=Sentiment.neutral,
            sentiment_score=0.0,
            rationale="Fake rationale.",
        )

    monkeypatch.setattr("services.analysis.analyse_article", fake_analyse_article)
