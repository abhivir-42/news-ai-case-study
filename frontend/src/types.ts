// The API contract in TypeScript. Mirrors backend/models.py and the Analysis
// table. Hand-written here; in production these would be generated from
// /openapi.json so they cannot drift from the server.

export interface Article {
    title: string
    description: string | null
    content: string | null
    url: string
    image: string | null
    published_at: string
    source_name: string
  }

  export interface Analysis {
    id: number
    url: string
    title: string
    source: string
    published_at: string
    summary: string
    sentiment: string
    sentiment_score: number
    created_at: string
  }

  // One article's verdict inside a bulk request. `analysis` is null exactly when
  // status is 'failed', which is why the batch can be part successful.
  export interface AnalysisOutcome {
    url: string
    status: 'created' | 'reused' | 'failed'
    analysis: Analysis | null
    error: string | null
  }
