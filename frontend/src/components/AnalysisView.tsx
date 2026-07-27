import type { Analysis } from '../types'

export function AnalysisView({ analysis }: { analysis: Analysis }) {
  return (
    <div className="analysis">
      <span className={`sentiment ${analysis.sentiment}`}>
        {analysis.sentiment} ({analysis.sentiment_score.toFixed(2)})
      </span>
      <p>{analysis.summary}</p>
    </div>
  )
}
