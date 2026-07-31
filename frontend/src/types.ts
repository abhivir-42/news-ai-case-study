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
