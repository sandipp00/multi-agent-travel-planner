import { useState, type FormEvent } from 'react'
import { useAuth } from '../lib/auth'

type Mode = 'login' | 'signup' | 'forgot'

const TITLES: Record<Mode, string> = {
  login: 'Log in',
  signup: 'Create your account',
  forgot: 'Reset your password',
}

// Supabase error codes -> messages a tester can act on.
const FRIENDLY_ERRORS: Record<string, string> = {
  over_email_send_rate_limit:
    'Too many emails were sent in the last hour, so we can’t send another one right now. Please try again in about an hour.',
  email_not_confirmed: 'Please confirm your email first — click the link we sent you, then log in.',
  invalid_credentials: 'That email and password don’t match. Try again, or use “Forgot password?”.',
  user_already_exists: 'An account with this email already exists. Log in instead.',
  weak_password: 'Please choose a stronger password (at least 8 characters).',
  email_address_invalid: 'That email address doesn’t look valid. Please check it.',
  over_request_rate_limit: 'Too many attempts. Please wait a minute and try again.',
}

function friendlyError(err: unknown): string {
  const code = (err as { code?: string } | null)?.code
  if (code && FRIENDLY_ERRORS[code]) return FRIENDLY_ERRORS[code]
  return err instanceof Error ? err.message : 'Something went wrong. Please try again.'
}

export function AuthPage() {
  const { supabase, googleEnabled } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
    setNotice(null)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      if (mode === 'login') {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      } else if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.origin },
        })
        if (error) throw error
        if (!data.session) {
          setNotice(`Almost done — we sent a confirmation link to ${email}. Click it, then log in.`)
          setMode('login')
        }
      } else {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin,
        })
        if (error) throw error
        setNotice(`If an account exists for ${email}, a password reset link is on its way.`)
      }
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setBusy(false)
    }
  }

  async function google() {
    if (!supabase) return
    setError(null)
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) setError(error.message)
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-mark" aria-hidden>✈</span> Trip Planner
        </div>
        <p className="muted">Real flight and hotel prices, weather and sights — planned by a team of AI agents.</p>

        <h1>{TITLES[mode]}</h1>

        {mode !== 'forgot' && googleEnabled && (
          <>
            <button type="button" className="button secondary full" onClick={google}>
              <span aria-hidden className="google-g">G</span> Continue with Google
            </button>
            <div className="divider"><span>or with email</span></div>
          </>
        )}

        <form onSubmit={submit} className="stack">
          <label>
            Email
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          {mode !== 'forgot' && (
            <label>
              Password
              <input
                type="password"
                required
                minLength={8}
                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {mode === 'signup' && <span className="hint">At least 8 characters.</span>}
            </label>
          )}
          {error && <p className="alert error" role="alert">{error}</p>}
          {notice && <p className="alert success" role="status">{notice}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : mode === 'signup' ? 'Sign up' : 'Send reset link'}
          </button>
        </form>

        <div className="auth-links">
          {mode === 'login' && (
            <>
              <button type="button" className="link" onClick={() => switchMode('forgot')}>Forgot password?</button>
              <span>New here? <button type="button" className="link" onClick={() => switchMode('signup')}>Create an account</button></span>
            </>
          )}
          {mode === 'signup' && (
            <span>Already have an account? <button type="button" className="link" onClick={() => switchMode('login')}>Log in</button></span>
          )}
          {mode === 'forgot' && (
            <button type="button" className="link" onClick={() => switchMode('login')}>Back to log in</button>
          )}
        </div>
      </div>
    </main>
  )
}
