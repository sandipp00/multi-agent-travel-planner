import type { ActivityOption, FlightOption, HotelOption, Sourced, ToolResult } from '../types'

// The raw specialist results behind a plan, shown as cards — straight from
// the data, not rewritten by the model, so every number can be checked.

const money = (value: unknown) =>
  typeof value === 'number' ? `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '?'

function unwrap<T>(result: unknown): { options: T[]; meta: Sourced<T> } {
  if (Array.isArray(result)) return { options: result as T[], meta: {} }
  const meta = (result ?? {}) as Sourced<T>
  return { options: Array.isArray(meta.options) ? meta.options : [], meta }
}

function SourceLine({ meta }: { meta: Sourced<unknown> }) {
  if (meta.error) return <p className="alert error">{meta.error}</p>
  return (
    <>
      {meta.warning && <p className="alert warning"><strong>Estimates only.</strong> {meta.warning.replace(/^ESTIMATES ONLY — /, '')}</p>}
      {meta.source && (
        <p className="muted small">
          Source: {meta.source}
          {meta.source_url && <> · <a href={meta.source_url} target="_blank" rel="noreferrer">open search</a></>}
        </p>
      )}
    </>
  )
}

function Link({ url }: { url?: string }) {
  return url ? <a href={url} target="_blank" rel="noreferrer" className="small">website ↗</a> : null
}

function Flights({ result }: { result: unknown }) {
  const { options, meta } = unwrap<FlightOption>(result)
  return (
    <section className="data-card">
      <h3>Flights</h3>
      <SourceLine meta={meta} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Airline</th><th>Price</th><th>Outbound</th><th>Trip time</th><th>Stops</th></tr>
          </thead>
          <tbody>
            {options.map((f, i) => (
              <tr key={i} className={(f.longest_layover_minutes ?? 0) >= 360 ? 'long-layover' : ''}>
                <td>{f.airline}</td>
                <td className="num">{money(f.price_usd)}</td>
                <td>{f.departure_time} → {f.arrival_time}</td>
                <td>{f.duration}</td>
                <td>{f.stops === 0 ? 'nonstop' : f.stops}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {options.some((f) => (f.longest_layover_minutes ?? 0) >= 360) && (
        <p className="muted small">Highlighted rows have a layover of 6+ hours.</p>
      )}
    </section>
  )
}

function Hotels({ result }: { result: unknown }) {
  const { options, meta } = unwrap<HotelOption>(result)
  return (
    <section className="data-card">
      <h3>Hotels</h3>
      <SourceLine meta={meta} />
      <ul className="option-list">
        {options.map((h, i) => (
          <li key={i}>
            <div className="option-head">
              <strong>{h.name}</strong>
              <span className="num">{money(h.price_per_night_usd)}/night</span>
            </div>
            <div className="muted small">
              {[h.area, h.total_usd != null && `${money(h.total_usd)} total`,
                h.rating != null && `★ ${h.rating}`, h.reviews != null && `${h.reviews.toLocaleString()} reviews`]
                .filter(Boolean).join(' · ')}
              {' '}<Link url={h.source_url} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Activities({ result }: { result: unknown }) {
  const { options, meta } = unwrap<ActivityOption>(result)
  return (
    <section className="data-card">
      <h3>Activities</h3>
      <SourceLine meta={meta} />
      <p className="muted small">Prices come from travel articles — treat them as rough.</p>
      <ul className="option-list">
        {options.map((a, i) => (
          <li key={i}>
            <div className="option-head">
              <strong>{a.name}</strong>
              <span className="num">{money(a.estimated_cost_usd)}</span>
            </div>
            <div className="muted small">
              {[a.category, a.duration_hours != null && `${a.duration_hours} h`].filter(Boolean).join(' · ')}{' '}
              <Link url={a.source_url} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

type Destination = {
  error?: string
  location?: string
  weather?: { error?: string; basis?: string; avg_high_c?: number; avg_low_c?: number; avg_high_f?: number; avg_low_f?: number; rainy_days?: number; days?: number }
  currency?: { error?: string; local_currency?: string; home_currency?: string; example?: string; as_of?: string }
  sights?: { name: string; type: string; website: string }[] | { error: string }
  guide?: { error?: string; summary?: string; url?: string }
}

function DestinationInfo({ result }: { result: unknown }) {
  const d = (result ?? {}) as Destination
  if (d.error) return <section className="data-card"><h3>Destination</h3><p className="alert error">{d.error}</p></section>
  const w = d.weather
  const c = d.currency
  return (
    <section className="data-card">
      <h3>Destination</h3>
      <p className="muted small">{d.location}</p>
      <div className="facts">
        <div>
          <span className="fact-label">Weather</span>
          {w && !w.error ? (
            <>
              <span>Highs ~{w.avg_high_f}°F ({w.avg_high_c}°C), lows ~{w.avg_low_f}°F ({w.avg_low_c}°C), rain on {w.rainy_days} of {w.days} days</span>
              <span className="muted small">{w.basis}</span>
            </>
          ) : <span className="muted">{w?.error ?? 'unavailable'}</span>}
        </div>
        <div>
          <span className="fact-label">Currency</span>
          {c && !c.error ? (
            <span>{c.local_currency}{c.example ? ` — ${c.example}` : ' (same as yours)'}</span>
          ) : <span className="muted">{c?.error ?? 'unavailable'}</span>}
        </div>
      </div>
      {Array.isArray(d.sights) && d.sights.length > 0 && (
        <>
          <span className="fact-label">Famous sights</span>
          <ul className="chips">
            {d.sights.map((s) => (
              <li key={s.name}>{s.website ? <a href={s.website} target="_blank" rel="noreferrer">{s.name}</a> : s.name}</li>
            ))}
          </ul>
        </>
      )}
      {d.guide && !d.guide.error && d.guide.url && (
        <p className="small"><a href={d.guide.url} target="_blank" rel="noreferrer">Wikivoyage travel guide ↗</a></p>
      )}
    </section>
  )
}

type Budget = { flight_cost_usd: number; hotel_total_usd: number; activities_cost_usd: number; total_cost_usd: number; budget_usd: number; remaining_usd: number; over_budget: boolean }

function BudgetBar({ result }: { result: unknown }) {
  const b = result as Budget
  if (!b || typeof b.total_cost_usd !== 'number') return null
  const scale = Math.max(b.budget_usd, b.total_cost_usd) || 1
  const part = (value: number) => `${(value / scale) * 100}%`
  return (
    <section className="data-card">
      <h3>Budget</h3>
      <div className="budget-bar" role="img" aria-label={`Spent ${money(b.total_cost_usd)} of ${money(b.budget_usd)}`}>
        <span className="seg flight" style={{ width: part(b.flight_cost_usd) }} />
        <span className="seg hotel" style={{ width: part(b.hotel_total_usd) }} />
        <span className="seg activities" style={{ width: part(b.activities_cost_usd) }} />
      </div>
      <ul className="legend small">
        <li><span className="dot flight" /> Flight {money(b.flight_cost_usd)}</li>
        <li><span className="dot hotel" /> Hotel {money(b.hotel_total_usd)}</li>
        <li><span className="dot activities" /> Activities {money(b.activities_cost_usd)}</li>
      </ul>
      <p className={b.over_budget ? 'alert error' : 'muted'}>
        Total <strong>{money(b.total_cost_usd)}</strong> of {money(b.budget_usd)} —{' '}
        {b.over_budget ? `${money(-b.remaining_usd)} over budget` : `${money(b.remaining_usd)} left`}
      </p>
    </section>
  )
}

const CARDS: Record<string, (props: { result: unknown }) => React.JSX.Element | null> = {
  search_flights: Flights,
  search_hotels: Hotels,
  search_activities: Activities,
  get_destination_info: DestinationInfo,
  analyze_budget: BudgetBar,
}

export function DataPanel({ data }: { data: ToolResult[] }) {
  // If a tool ran more than once (e.g. budget re-checked), show its latest result.
  const latest = new Map<string, unknown>()
  for (const [name, , result] of data) latest.set(name, result)
  const order = ['analyze_budget', 'search_flights', 'search_hotels', 'get_destination_info', 'search_activities']
  return (
    <div className="data-panel">
      {order.filter((name) => latest.has(name)).map((name) => {
        const Card = CARDS[name]
        return <Card key={name} result={latest.get(name)} />
      })}
    </div>
  )
}
