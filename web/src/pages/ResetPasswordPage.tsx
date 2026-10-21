import { useState, type FormEvent } from 'react'
import { useAuth } from '../lib/auth'

/** Shown after the user opens the password-reset link from their email. */
export function ResetPasswordPage() {
  const { supabase, clearRecovering } = useAuth()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase) return
    setBusy(true)
    setError(null)
    const { error } = await supabase.auth.updateUser({ password })
    setBusy(false)
    if (error) setError(error.message)
    else clearRecovering()
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <h1>Choose a new password</h1>
        <form onSubmit={submit} className="stack">
          <label>
            New password
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <span className="hint">At least 8 characters.</span>
          </label>
          {error && <p className="alert error" role="alert">{error}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saving…' : 'Save new password'}
          </button>
        </form>
      </div>
    </main>
  )
}
