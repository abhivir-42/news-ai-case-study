// All application state lives here: query, articles, analyses, and the three
// in-flight flags. Child components are stateless and receive props.
// useEffect with an empty dependency array loads history once, on mount.

import { useEffect, useState } from 'react'
import './App.css'
import {
  MAX_BULK_ARTICLES,
  createAnalyses,
  createAnalysis,
  listAnalyses,
  searchArticles,
} from './api'
import { AnalysisView } from './components/AnalysisView'
import { ArticleCard } from './components/ArticleCard'
import type { Analysis, Article } from './types'

function App() {
  const [query, setQuery] = useState('')
  const [articles, setArticles] = useState<Article[]>([])
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading, setLoading] = useState(false)
  const [analysingUrl, setAnalysingUrl] = useState<string | null>(null)
  const [analysingAll, setAnalysingAll] = useState(false)
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

  async function handleAnalyseAll() {
    setAnalysingAll(true)
    setError(null)
    try {
      const outcomes = await createAnalyses(articles)
      // A batch can be part successful, so take the analyses that came back and
      // report the rest rather than treating the whole request as failed.
      const analysed = outcomes.flatMap((outcome) =>
        outcome.analysis ? [outcome.analysis] : [],
      )
      setAnalyses((current) => [
        ...analysed,
        ...current.filter((item) => !analysed.some((row) => row.id === item.id)),
      ])

      const failed = outcomes.filter((outcome) => outcome.status === 'failed')
      if (failed.length > 0) {
        setError(`${failed.length} of ${outcomes.length} articles could not be analysed.`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analyse failed')
    } finally {
      setAnalysingAll(false)
    }
  }

  const analysisByUrl = new Map(analyses.map((item) => [item.url, item]))
  const bulkCount = Math.min(articles.length, MAX_BULK_ARTICLES)

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
          <button onClick={handleAnalyseAll} disabled={analysingAll}>
            {analysingAll ? 'Analysing…' : `Analyse all ${bulkCount}`}
          </button>
          <ul className="articles">
            {articles.map((article) => (
              <ArticleCard
                key={article.url}
                article={article}
                analysis={analysisByUrl.get(article.url)}
                isAnalysing={analysingAll || analysingUrl === article.url}
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
