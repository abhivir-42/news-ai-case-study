// Renders one stored analysis. Used in both the results list and the history
// list, so the two can never drift apart.

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
