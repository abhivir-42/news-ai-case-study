import type { Analysis, Article } from '../types'
import { AnalysisView } from './AnalysisView'

interface ArticleCardProps {
  article: Article
  analysis?: Analysis
  isAnalysing: boolean
  onAnalyse: (article: Article) => void
}

export function ArticleCard({
  article,
  analysis,
  isAnalysing,
  onAnalyse,
}: ArticleCardProps) {
  return (
    <li>
      <a href={article.url} target="_blank" rel="noreferrer">
        {article.title}
      </a>
      <p className="meta">
        {article.source_name} ·{' '}
        {new Date(article.published_at).toLocaleDateString()}
      </p>

      {analysis ? (
        <AnalysisView analysis={analysis} />
      ) : (
        <button onClick={() => onAnalyse(article)} disabled={isAnalysing}>
          {isAnalysing ? 'Analysing…' : 'Analyse'}
        </button>
      )}
    </li>
  )
}
