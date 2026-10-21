import { useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Turn } from '../types'
import { DataPanel } from './DataPanel'
import { FeedbackWidget } from './FeedbackWidget'

/** One exchange: the traveler's message, the plan, its data, and feedback. */
export function TurnView({ turn }: { turn: Turn }) {
  const [showData, setShowData] = useState(true)
  const hasData = turn.data.length > 0
  return (
    <article className="turn">
      <div className="bubble user">{turn.request}</div>
      <div className="bubble planner">
        <div className="markdown">
          <Markdown remarkPlugins={[remarkGfm]}
            components={{ a: (props) => <a {...props} target="_blank" rel="noreferrer" /> }}>
            {turn.reply}
          </Markdown>
        </div>

        {turn.issues.length > 0 && (
          <div className="alert warning">
            <strong>Fact check:</strong> these statements don’t match the data below — trust the data.
            <ul>{turn.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
          </div>
        )}

        {hasData && (
          <>
            <button type="button" className="link small" onClick={() => setShowData(!showData)} aria-expanded={showData}>
              {showData ? 'Hide' : 'Show'} the data behind this plan
            </button>
            {showData && <DataPanel data={turn.data} />}
          </>
        )}

        <FeedbackWidget planId={turn.plan_id} initial={turn.feedback} />
      </div>
    </article>
  )
}
