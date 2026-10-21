import { useState } from 'react'
import { api } from '../lib/api'
import type { Feedback } from '../types'

const FLAGS: [string, string][] = [
  ['prices_wrong', 'Prices looked wrong'],
  ['itinerary_confusing', "Itinerary didn't make sense"],
  ['missing_info', 'Something was missing'],
]

/** Thumbs up/down, quick flags, and a comment — saved with the plan. */
export function FeedbackWidget({ planId, initial }: { planId: string; initial: Feedback }) {
  const [rating, setRating] = useState<number | null>(initial.rating)
  const [flags, setFlags] = useState<string[]>(initial.flags)
  const [comment, setComment] = useState(initial.comment)
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>(initial.rating != null ? 'saved' : 'idle')

  async function save(next: Partial<Feedback> = {}) {
    const body = { rating, flags, comment, ...next }
    setState('saving')
    try {
      await api.feedback(planId, body)
      setState('saved')
    } catch {
      setState('error')
    }
  }

  function rate(value: number) {
    const next = rating === value ? null : value
    setRating(next)
    void save({ rating: next })
  }

  function toggle(flag: string) {
    const next = flags.includes(flag) ? flags.filter((f) => f !== flag) : [...flags, flag]
    setFlags(next)
    void save({ flags: next })
  }

  return (
    <div className="feedback">
      <span className="small">Was this plan helpful?</span>
      <button type="button" className={`thumb ${rating === 1 ? 'active' : ''}`} aria-pressed={rating === 1} onClick={() => rate(1)}>👍</button>
      <button type="button" className={`thumb ${rating === -1 ? 'active' : ''}`} aria-pressed={rating === -1} onClick={() => rate(-1)}>👎</button>
      {rating !== null && (
        <div className="feedback-more">
          <div className="flag-row">
            {FLAGS.map(([key, label]) => (
              <label key={key} className="check small">
                <input type="checkbox" checked={flags.includes(key)} onChange={() => toggle(key)} /> {label}
              </label>
            ))}
          </div>
          <div className="comment-row">
            <input
              placeholder="Anything else? (optional)"
              value={comment}
              maxLength={2000}
              onChange={(e) => { setComment(e.target.value); setState('idle') }}
            />
            <button type="button" className="button secondary small" onClick={() => void save()}>Send</button>
          </div>
        </div>
      )}
      <span className="muted small feedback-state">
        {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Thanks — saved.' : state === 'error' ? "Couldn't save, try again." : ''}
      </span>
    </div>
  )
}
