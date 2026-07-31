from types import SimpleNamespace

import pytest

import services.ai as ai_service
import services.analysis as analysis_service
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


def test_create_analysis_returns_502_when_ai_fails(client, monkeypatch):
    """An AI provider failure is an upstream failure, so it maps to 502 like GNews does."""

    def boom(title, description, content):
        raise AIProviderError("model returned no parsed output")

    monkeypatch.setattr("services.analysis.analyse_article", boom)
    response = client.post("/api/analyses", json=SAMPLE_ARTICLE)
    assert response.status_code == 502


def test_list_analyses_returns_stored_rows(client, fake_ai):
    client.post("/api/analyses", json=SAMPLE_ARTICLE)
    response = client.get("/api/analyses")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_analysis_returns_404_when_missing(client):
    assert client.get("/api/analyses/999999").status_code == 404


def test_search_articles_requires_query(client):
    assert client.get("/api/articles").status_code == 422


def test_search_articles_returns_502_when_provider_fails(client, monkeypatch):
    async def boom(query, max_results=10):
        raise NewsProviderError("upstream down")

    monkeypatch.setattr("main.search_news", boom)
    response = client.get("/api/articles?q=openai")
    assert response.status_code == 502
