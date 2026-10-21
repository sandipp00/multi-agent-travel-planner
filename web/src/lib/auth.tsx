import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getPublicConfig, getSupabase } from './supabase'

type AuthState = {
  supabase: SupabaseClient | null
  session: Session | null
  loading: boolean
  googleEnabled: boolean
  setupError: string | null
  // True after the user opens a password-reset link from their email.
  recovering: boolean
  clearRecovering: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [googleEnabled, setGoogleEnabled] = useState(false)
  const [setupError, setSetupError] = useState<string | null>(null)
  const [recovering, setRecovering] = useState(false)

  useEffect(() => {
    let unsubscribe = () => {}
    getSupabase()
      .then(async (client) => {
        setSupabase(client)
        setGoogleEnabled((await getPublicConfig()).google_enabled)
        const { data } = await client.auth.getSession()
        setSession(data.session)
        const { data: listener } = client.auth.onAuthStateChange((event, next) => {
          setSession(next)
          if (event === 'PASSWORD_RECOVERY') setRecovering(true)
        })
        unsubscribe = () => listener.subscription.unsubscribe()
      })
      .catch((error: Error) => setSetupError(error.message))
      .finally(() => setLoading(false))
    return () => unsubscribe()
  }, [])

  return (
    <AuthContext.Provider
      value={{ supabase, session, loading, googleEnabled, setupError, recovering, clearRecovering: () => setRecovering(false) }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
