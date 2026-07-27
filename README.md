# News AI — topic search, AI summary & sentiment

Search recent news on any topic, analyse how a story is being covered, and keep a running
history of every analysis.

| | |
|---|---|
| **Live app** | https://news-ai-case-study.vercel.app |
| **API** | https://news-ai-case-study.onrender.com |
| **API docs** | https://news-ai-case-study.onrender.com/docs |

> ⏳ The API runs on Render's free tier and spins down when idle — **the first request after a
> period of inactivity can take ~50 seconds** while it wakes up. Subsequent requests are fast.

---

## What it does

1. **Search** a topic — the backend queries [GNews](https://gnews.io) and returns recent articles.
2. **Analyse** any article you care about — one OpenAI call returns a summary, a sentiment
   classification, and a confidence score.
3. **Store** every analysis in Postgres.
4. **History** — all past analyses, newest first, persisted across sessions.

### Why analysis is on-demand, not automatic

Analysing every search result would burn API budget on articles nobody reads. Making
**Analyse** an explicit action respects user intent and keeps cost proportional to value.
Re-analysing an article that's already stored is free — the API returns the stored result
instead of calling OpenAI again.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python) | Typed request/response models via Pydantic, auto-generated OpenAPI docs |
| Database | **Postgres** (Supabase) via **SQLModel** | Relational data with a fixed shape; SQLModel is SQLAlchemy + Pydantic in one model |
| AI | **OpenAI `gpt-4.1-nano`** with Structured Outputs | Schema-guaranteed JSON — no parsing of free text |
| Frontend | **React + TypeScript** (Vite) | Types mirror the API contract; compile-time safety across the boundary |
| Hosting | **Render** (API) + **Vercel** (SPA) | Each host matches its workload: a long-running server vs. static files on a CDN |

---

## Architecture

```
React SPA (Vercel)
      │  JSON over HTTPS
      ▼
FastAPI (Render)
      │
      ├── main.py                 routes only — parse, delegate, set status
      ├── models.py               API schemas
      ├── config.py               validated settings from the environment
      ├── database.py             engine, Analysis table, session dependency
      └── services/
            ├── news.py           GNews client + response normalisation
            ├── ai.py             OpenAI structured analysis
            └── analysis.py       dedup, orchestration, queries
                    │
                    ▼
          Postgres (Supabase)
```

**Three rules the layering follows:**

1. **Routes orchestrate, services implement.** A handler reads the request, calls a service,
   and returns a response. No business logic lives in `main.py`.
2. **Services never mention HTTP.** `news.py` raises `NewsProviderError`; the route translates
   it into a `502`. This keeps services testable and reusable outside a web request.
3. **Services return facts, routes decide status.** `get_or_create_analysis()` returns
   `(analysis, created)`; the route turns `created` into `201` vs `200`.

---

## API

| Method | Path | Behaviour |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/articles?q=<topic>` | Search news. `422` if `q` missing · `502` if the provider fails |
| `POST` | `/api/analyses` | Analyse and store an article. **`201`** when created, **`200`** when an analysis for that URL already exists |
| `GET` | `/api/analyses?limit=<n>` | Stored analyses, newest first |
| `GET` | `/api/analyses/{id}` | A single analysis. `404` if not found |

An analysis is modelled as a **resource** (`POST /api/analyses` creates one) rather than an
action endpoint like `/summarise`, so the collection is addressable, cacheable, and reads
consistently with the rest of the API.

### AI output contract

The model is constrained by a JSON schema, so `sentiment` can only ever be one of three values:

```jsonc
{
  "summary": "Two-sentence summary of the coverage.",
  "sentiment": "positive | neutral | negative",  // enum, enforced
  "sentiment_score": 0.8,                        // -1.0 … 1.0
  "rationale": "One sentence explaining the classification."
}
```

Using Structured Outputs rather than parsing free text means the response cannot drift into
`"mostly positive"` or `"POSITIVE!"`, and no defensive parsing code is needed.

---

## Running locally

**Requirements:** Python 3.12+, Node 20+, a Postgres database, a
[GNews API key](https://gnews.io), an OpenAI API key.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `backend/.env`:

```
GNEWS_API_KEY=your_key
OPENAI_API_KEY=your_key
DATABASE_URL=postgresql://user:password@host:5432/dbname
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

```bash
fastapi dev main.py          # http://127.0.0.1:8000/docs
```

The `analysis` table is created automatically at startup.

### Frontend

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

`VITE_API_URL` defaults to `http://127.0.0.1:8000`; set it to override.

### Tests

```bash
cd backend && pytest -v
```

Seven tests covering the happy path, dedup behaviour, validation, and upstream failure
handling. They run against an in-memory SQLite database with the OpenAI call stubbed, so the
suite is fast, free, and deterministic — no network access required.

---

## Notable decisions

**Dedup is enforced twice.** `url` is a `UNIQUE` column *and* the service checks before
inserting. The check is the fast path that avoids a paid OpenAI call; the constraint is the
guarantee that survives concurrent requests.

**Secrets never appear in logs.** Settings are typed as `SecretStr`, so they render as
`**********` in tracebacks and require an explicit `.get_secret_value()` to read.

**The API normalises the news provider's response.** GNews's shape is mapped into our own
`Article` model rather than passed through. Swapping providers means changing one mapping
function — not every endpoint and component.

**CORS origins are configuration, not code.** The allowed origin list is read from the
environment, so production and local development differ by config alone.

---

## Known limitations & what I'd change for production

| Limitation | Production approach |
|---|---|
| The OpenAI call blocks the HTTP request for several seconds | Enqueue it as a background job and push the result to the client via websocket/SSE |
| GNews's free tier truncates article `content`, so summaries reflect the headline, description and a snippet rather than the full article | Use a provider with full text, or fetch and extract the article body |
| `SQLModel.create_all()` creates tables but cannot alter them | Alembic migrations — versioned, reviewable, reversible |
| No retries, backoff, or circuit breaker on external calls | Wrap the GNews/OpenAI clients with retry + backoff and cache responses in Redis |
| `limit` caps page size but there's no pagination | Cursor-based pagination with a total count |
| Tests run against SQLite while production is Postgres | A real Postgres test database (e.g. testcontainers) |
| No AI evaluation or tracing | Prompt versioning, an eval set, and per-call cost/latency tracing |
