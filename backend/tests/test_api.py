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
