import { useState, type FormEvent } from 'react'

/** Structured helper that writes a complete trip request for the planner. */
export function TripForm({ disabled, onSubmit }: { disabled: boolean; onSubmit: (message: string) => void }) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [budget, setBudget] = useState('')
  const [interests, setInterests] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    let message =
      `Plan a trip from ${from.trim()} to ${to.trim()}, ${start} to ${end}, ` +
      `budget $${budget} covering flight, hotel and activities.`
    if (interests.trim()) message += ` I like ${interests.trim()}.`
    onSubmit(message)
  }

  return (
    <form className="trip-form" onSubmit={submit}>
      <label>
        From
        <input required placeholder="London (LHR)" value={from} onChange={(e) => setFrom(e.target.value)} />
      </label>
      <label>
        To
        <input required placeholder="Marrakesh" value={to} onChange={(e) => setTo(e.target.value)} />
      </label>
      <label>
        Depart
        <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} />
      </label>
      <label>
        Return
        <input required type="date" min={start || undefined} value={end} onChange={(e) => setEnd(e.target.value)} />
      </label>
      <label>
        Budget (USD)
        <input required type="number" min={100} step={50} placeholder="1500" value={budget} onChange={(e) => setBudget(e.target.value)} />
      </label>
      <label className="wide">
        Interests <span className="hint">(optional)</span>
        <input placeholder="markets, gardens, food" value={interests} onChange={(e) => setInterests(e.target.value)} />
      </label>
      <button className="button primary" disabled={disabled}>Plan my trip</button>
    </form>
  )
}
