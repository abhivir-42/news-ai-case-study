import { useEffect, useState } from 'react'
import './App.css'
import { createAnalysis, listAnalyses, searchArticles } from './api'
import { AnalysisView } from './components/AnalysisView'
import { ArticleCard } from './components/ArticleCard'
import type { Analysis, Article } from './types'

function App() {
  const [query, setQuery] = useState('')
  const [articles, setArticles] = useState<Article[]>([])
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading, setLoading] = useState(false)
  const [analysingUrl, setAnalysingUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listAnalyses()
      .then(setAnalyses)
      .catch(() => setError('Could not load history'))
  }, [])

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setArticles(await searchArticles(query))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleAnalyse(article: Article) {
    setAnalysingUrl(article.url)
    setError(null)
    try {
      const analysis = await createAnalysis(article)
      setAnalyses((current) => [
        analysis,
        ...current.filter((item) => item.id !== analysis.id),
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setAnalysingUrl(null)
    }
  }

  const analysisByUrl = new Map(analyses.map((item) => [item.url, item]))

  return (
    <main>
      <h1>News AI</h1>
      <p className="tagline">Search a topic, analyse how it's being covered.</p>

      <form onSubmit={handleSearch}>
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

      {articles.length > 0 && (
        <section>
          <h2>Results</h2>
          <ul className="articles">
            {articles.map((article) => (
              <ArticleCard
                key={article.url}
                article={article}
                analysis={analysisByUrl.get(article.url)}
                isAnalysing={analysingUrl === article.url}
                onAnalyse={handleAnalyse}
              />
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>History</h2>
        {analyses.length === 0 ? (
          <p className="muted">No analyses yet — search a topic and analyse an article.</p>
        ) : (
          <ul className="articles">
            {analyses.map((analysis) => (
              <li key={analysis.id}>
                <a href={analysis.url} target="_blank" rel="noreferrer">
                  {analysis.title}
                </a>
                <p className="meta">{analysis.source}</p>
                <AnalysisView analysis={analysis} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}

export default App
