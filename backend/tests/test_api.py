from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

import dependencies
from database import Analysis, get_session
from main import app
from services.ratelimit import SlidingWindowLimiter

import services.ai as ai_service
import services.analysis as analysis_service
import services.news as news_service
from services.ai import AIProviderError
from services.news import NewsProviderError

SAMPLE_ARTICLE = {
    "title": "Company X reports record profits",
    "description": "Revenue jumped 40%.",
    "content": "Executives credited new product lines.",
    "url": "https://example.com/record-profits",
    "image": None,
    "published_at": "2026-07-25T00:00:00Z",
    "source_name": "Test Source",
}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_database_answers(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_is_down(client):
    """Readiness must fail when the database does, or the probe is decorative."""

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    app.dependency_overrides[get_session] = lambda: _BrokenSession()
    assert client.get("/ready").status_code == 503


def test_health_does_not_touch_the_database(client):
    """Liveness stays cheap: it must still answer while the database is down."""

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    app.dependency_overrides[get_session] = lambda: _BrokenSession()
    assert client.get("/health").status_code == 200


def test_created_at_is_indexed():
    """Every read of the feed orders by created_at, so it must not be a full scan."""
    indexed = {column.name for index in Analysis.__table__.indexes for column in index.columns}
    assert "created_at" in indexed


def test_create_analysis_returns_201(client, fake_ai):
    response = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == "Fake summary."
    assert body["sentiment"] == "neutral"
    assert body["id"] is not None


def test_create_analysis_is_deduplicated(client, fake_ai):
    first = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    second = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_concurrent_insert_does_not_500(client, fake_ai, monkeypatch):
    """Two requests race: both dedup checks miss, so both try to INSERT the same URL.

    The unique index rejects the second write. The endpoint must recover and return the
    row that won, not surface an IntegrityError as a 500.
    """
    first = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert first.status_code == 201

    # Reproduce the interleaving: the dedup check misses once, then the lookup that
    # runs after the constraint fires behaves normally and finds the winning row.
    real_find = analysis_service._find_by_url
    calls = {"n": 0}

    def find_missing_once(session, url):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(session, url)

    monkeypatch.setattr(analysis_service, "_find_by_url", find_missing_once)

    second = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_analyse_article_raises_when_model_returns_no_parsed_output(monkeypatch):
    """The SDK returns parsed=None on a refusal or a length stop. Do not hand that on."""
    empty = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None), finish_reason="length")]
    )
    monkeypatch.setattr(
        ai_service,
        "client",
        SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=lambda **kwargs: empty))
        ),
    )
    with pytest.raises(AIProviderError):
        ai_service.analyse_article("Title", "Description", "Content")


def test_analyse_article_wraps_sdk_errors(monkeypatch):
    """Once the SDK has exhausted its retries, its exception is an upstream failure."""

    def raise_timeout(**kwargs):
        raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))

    monkeypatch.setattr(
        ai_service,
        "client",
        SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=raise_timeout))
        ),
    )
    with pytest.raises(AIProviderError):
        ai_service.analyse_article("Title", "Description", "Content")


def test_openai_client_is_bounded():
    """A call in the request path must not wait forever."""
    assert ai_service.OPENAI_TIMEOUT_SECONDS <= 30
    assert ai_service.OPENAI_MAX_RETRIES >= 1


def test_create_analysis_returns_502_when_ai_fails(client, monkeypatch):
    """An AI provider failure is an upstream failure, so it maps to 502 like GNews does."""

    def boom(title, description, content):
        raise AIProviderError("model returned no parsed output")

    monkeypatch.setattr("services.analysis.analyse_article", boom)
    response = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert response.status_code == 502


def test_limiter_allows_up_to_the_limit_then_reports_wait():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.check("1.2.3.4") is None
    assert limiter.check("1.2.3.4") is None
    retry_after = limiter.check("1.2.3.4")
    assert retry_after is not None and 0 < retry_after <= 60
    # A different client has its own budget.
    assert limiter.check("5.6.7.8") is None


def test_analyse_endpoint_returns_429_over_the_limit(client, fake_ai, monkeypatch):
    """The endpoint that spends money must be capped."""
    monkeypatch.setattr(dependencies.analyse_limiter, "limit", 1)
    monkeypatch.setattr(dependencies.analyse_limiter, "_hits", {})

    assert client.post("/api/analyses", json=SAMPLE_ARTICLE).status_code == 201
    blocked = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_prompt_input_is_clipped(monkeypatch):
    """A long article must not become an unpriced request."""
    captured = {}

    def capture(**kwargs):
        captured["messages"] = kwargs["messages"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=ai_service.ArticleAnalysis(
                            summary="s",
                            sentiment=ai_service.Sentiment.neutral,
                            sentiment_score=0.0,
                            rationale="r",
                        )
                    ),
                    finish_reason="stop",
                )
            ]
        )

    monkeypatch.setattr(
        ai_service,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=capture))),
    )
    ai_service.analyse_article("Title", "d" * 50_000, "c" * 50_000)

    prompt = captured["messages"][1]["content"]
    assert len(prompt) < (
        ai_service.MAX_DESCRIPTION_CHARS + ai_service.MAX_CONTENT_CHARS + 500
    )


def test_cache_hit_is_logged(client, fake_ai, caplog):
    """The dedup hit rate is the metric that justifies get_or_create."""
    client.post("/api/analyses", json=SAMPLE_ARTICLE)
    with caplog.at_level("INFO"):
        client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert "event=analysis.cache_hit" in caplog.text


def test_request_id_is_echoed(client):
    """A caller-supplied id is honoured so a trace can span frontend and API."""
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
    assert client.get("/health").headers["X-Request-ID"]


def test_list_analyses_returns_stored_rows(client, fake_ai):
    client.post("/api/analyses", json=SAMPLE_ARTICLE)
    response = client.get("/api/analyses")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_analysis_returns_404_when_missing(client):
    assert client.get("/api/analyses/999999").status_code == 404


def test_search_articles_requires_query(client):
    assert client.get("/api/articles").status_code == 422


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _fake_gnews(monkeypatch, response=None, error=None):
    """Replace the httpx client used by services/news.py with a canned response."""

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, params=None):
            if error is not None:
                raise error
            return response

    monkeypatch.setattr(news_service.httpx, "AsyncClient", lambda **kwargs: _FakeClient())


def test_search_articles_returns_502_on_malformed_article(client, monkeypatch):
    """One article missing required fields must not take the whole request down."""
    _fake_gnews(monkeypatch, _FakeResponse(payload={"articles": [{"title": "no url here"}]}))
    assert client.get("/api/articles?q=india").status_code == 502


def test_search_articles_returns_502_when_body_has_no_articles(client, monkeypatch):
    """A 200 carrying an error body is still a provider failure."""
    _fake_gnews(monkeypatch, _FakeResponse(payload={"errors": ["invalid api key"]}))
    assert client.get("/api/articles?q=india").status_code == 502


def test_search_articles_returns_502_on_network_error(client, monkeypatch):
    """A timeout or connection failure is upstream's problem, not a server bug."""
    _fake_gnews(monkeypatch, error=news_service.httpx.ConnectTimeout("timed out"))
    assert client.get("/api/articles?q=india").status_code == 502


def test_search_articles_returns_502_when_provider_fails(client, monkeypatch):
    async def boom(query, max_results=10):
        raise NewsProviderError("upstream down")

    monkeypatch.setattr("main.search_news", boom)
    response = client.get("/api/articles?q=openai")
    assert response.status_code == 502
