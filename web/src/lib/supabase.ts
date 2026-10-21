import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// The Supabase URL and publishable key come from the backend (/api/config),
// so there's a single .env file for the whole project.
export type PublicConfig = {
  supabase_url: string
  supabase_publishable_key: string
  // Whether "Continue with Google" is switched on in the Supabase project.
  google_enabled: boolean
}

let client: SupabaseClient | null = null
let publicConfig: PublicConfig | null = null

export async function getPublicConfig(): Promise<PublicConfig> {
  if (publicConfig) return publicConfig
  const response = await fetch('/api/config')
  if (!response.ok) throw new Error('The backend is not running (couldn’t load /api/config).')
  publicConfig = (await response.json()) as PublicConfig
  return publicConfig
}

export async function getSupabase(): Promise<SupabaseClient> {
  if (client) return client
  const config = await getPublicConfig()
  if (!config.supabase_url || !config.supabase_publishable_key) {
    throw new Error('Login is not set up yet: add SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY to .env.')
  }
  client = createClient(config.supabase_url, config.supabase_publishable_key)
  return client
}
