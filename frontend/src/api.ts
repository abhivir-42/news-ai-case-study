import type { Analysis, Article } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function searchArticles(query: string) {
  return request<Article[]>(`/api/articles?q=${encodeURIComponent(query)}`)
}

export function createAnalysis(article: Article) {
  return request<Analysis>('/api/analyses', {
    method: 'POST',
    body: JSON.stringify(article),
  })
}

export function listAnalyses(limit = 20) {
  return request<Analysis[]>(`/api/analyses?limit=${limit}`)
}
