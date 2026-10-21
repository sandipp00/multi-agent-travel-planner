import type { ConversationSummary, Feedback, Me, StreamEvent, Turn } from '../types'
import { getSupabase } from './supabase'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = await getSupabase()
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()), ...init.headers },
  })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return response.json()
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return 'Please check your message and try again.'
  } catch {
    // not JSON
  }
  return `Request failed (${response.status}).`
}

export const api = {
  me: () => request<Me>('/api/me'),
  conversations: () => request<ConversationSummary[]>('/api/conversations'),
  conversation: (id: string) => request<{ id: string; title: string; turns: Turn[] }>(`/api/conversations/${id}`),
  feedback: (planId: string, feedback: Feedback) =>
    request<{ ok: boolean }>(`/api/plans/${planId}/feedback`, { method: 'POST', body: JSON.stringify(feedback) }),
  adminPlans: () =>
    request<{ plans: AdminPlan[]; site_plans_today: number; site_plans_limit: number }>('/api/admin/plans'),
}

export type AdminPlan = {
  id: string
  user_email: string
  request: string
  reply: string
  issues: string[]
  used_tools: boolean
  duration_ms: number
  rating: number | null
  comment: string
  flags: string[]
  created_at: string
}

/** Send a chat message and call `onEvent` for each streamed line (NDJSON). */
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })
  if (!response.ok || !response.body) throw new ApiError(response.status, await errorMessage(response))

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line))
    if (done) break
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}
