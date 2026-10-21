import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AdminPlan } from '../lib/api'

const FLAG_LABELS: Record<string, string> = {
  prices_wrong: 'prices wrong',
  itinerary_confusing: 'itinerary confusing',
  missing_info: 'missing info',
}

/** Every plan testers made, with their feedback — to see where the planner fails. */
export function AdminPage() {
  const [data, setData] = useState<{ plans: AdminPlan[]; site_plans_today: number; site_plans_limit: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    api.adminPlans().then(setData).catch((err: Error) => setError(err.message))
  }, [])

  const plans = data?.plans ?? []
  const rated = plans.filter((p) => p.rating != null)
  const thumbsUp = rated.filter((p) => p.rating === 1).length

  return (
    <div className="admin">
      <header className="topbar">
        <div className="brand"><span className="brand-mark" aria-hidden>✈</span> Trip Planner · Admin</div>
        <Link to="/" className="link small">← Back to planner</Link>
      </header>
      <main className="admin-main">
        {error && <p className="alert error">{error}</p>}
        {data && (
          <div className="stats">
            <div><span className="stat">{data.site_plans_today}/{data.site_plans_limit}</span><span className="muted small">plans today (site-wide)</span></div>
            <div><span className="stat">{plans.length}</span><span className="muted small">messages, all time</span></div>
            <div><span className="stat">{rated.length ? `${Math.round((thumbsUp / rated.length) * 100)}%` : '—'}</span><span className="muted small">👍 of {rated.length} rated</span></div>
            <div><span className="stat">{plans.filter((p) => p.issues.length > 0).length}</span><span className="muted small">plans with fact-check issues</span></div>
          </div>
        )}
        <div className="table-wrap">
          <table className="admin-table">
            <thead>
              <tr><th>When</th><th>Who</th><th>Request</th><th>Rating</th><th>Feedback</th><th>Issues</th><th>Time</th></tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <Fragment key={p.id}>
                  <tr onClick={() => setOpen(open === p.id ? null : p.id)} className="clickable">
                    <td className="nowrap">{new Date(p.created_at).toLocaleString()}</td>
                    <td>{p.user_email}</td>
                    <td className="request">{p.request}</td>
                    <td>{p.rating === 1 ? '👍' : p.rating === -1 ? '👎' : ''}</td>
                    <td>
                      {p.flags.map((f) => <span key={f} className="tag">{FLAG_LABELS[f] ?? f}</span>)}
                      {p.comment && <div className="small">{p.comment}</div>}
                    </td>
                    <td className="num">{p.issues.length || ''}</td>
                    <td className="num nowrap">{p.used_tools ? `${Math.round(p.duration_ms / 1000)}s` : 'chat'}</td>
                  </tr>
                  {open === p.id && (
                    <tr className="detail">
                      <td colSpan={7}>
                        {p.issues.length > 0 && <ul className="small">{p.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
                        <pre>{p.reply}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {data && plans.length === 0 && <p className="muted">No plans yet.</p>}
      </main>
    </div>
  )
}
