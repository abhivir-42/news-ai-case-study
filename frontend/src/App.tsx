import { useState } from 'react'
import './App.css'
import type { Article } from './types'

const API_URL = 'http://127.0.0.1:8000'

function App() {
  const [query, setQuery] = useState('')
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `${API_URL}/api/articles?q=${encodeURIComponent(query)}`
      )
      if (!response.ok) {
        throw new Error(`Search failed (${response.status})`)
      }
      const data: Article[] = await response.json()
      setArticles(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>News AI</h1>

      <form onSubmit={handleSubmit}>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search a topic, e.g. openai"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <ul className="articles">
        {articles.map((article) => (
          <li key={article.url}>
            <a href={article.url} target="_blank" rel="noreferrer">
              {article.title}
            </a>
            <p>
              {article.source_name} ·{' '}
              {new Date(article.published_at).toLocaleDateString()}
            </p>
          </li>
        ))}
      </ul>
    </main>
  )
}

export default App
