import type { ProgressStep } from '../types'

/** Live list of specialist agents while a plan is being made. */
export function AgentProgress({ steps, checking }: { steps: ProgressStep[]; checking: boolean }) {
  return (
    <div className="progress" aria-live="polite">
      <p className="progress-title">
        <span className="spinner" aria-hidden /> Planning your trip — this usually takes about a minute
      </p>
      {steps.length === 0 && <p className="muted small">The planner is reading your request…</p>}
      <ul>
        {steps.map((step) => (
          <li key={step.call_id} className={`step ${step.status} ${step.ok === false ? 'failed' : ''}`}>
            <span className="step-icon" aria-hidden>
              {step.status === 'started' ? '…' : step.ok === false ? '!' : '✓'}
            </span>
            <span className="step-label">{step.label}</span>
            <span className="step-summary">{step.status === 'started' ? 'working…' : step.summary}</span>
          </li>
        ))}
        {checking && (
          <li className="step started">
            <span className="step-icon" aria-hidden>…</span>
            <span className="step-label">Fact check</span>
            <span className="step-summary">checking the plan against the data…</span>
          </li>
        )}
      </ul>
    </div>
  )
}
