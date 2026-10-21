// Shapes of the backend's JSON (see server/app.py and src/agents/*).

export type Usage = {
  plans_today: number
  plans_limit: number
  messages_today: number
  messages_limit: number
  site_plans_today: number
  site_plans_limit: number
}

export type Me = { email: string; is_admin: boolean; usage: Usage }

// One specialist call: [tool name, arguments, result].
export type ToolResult = [string, Record<string, unknown>, unknown]

export type Feedback = { rating: number | null; comment: string; flags: string[] }

export type Turn = {
  plan_id: string
  request: string
  reply: string
  data: ToolResult[]
  issues: string[]
  feedback: Feedback
}

export type ConversationSummary = { id: string; title: string; updated_at: string }

export type ProgressStep = {
  call_id: string
  tool: string
  label: string
  status: 'started' | 'finished'
  ok?: boolean
  summary?: string
}

export type StreamEvent =
  | { type: 'progress'; status: 'started'; tool: string; call_id: string; label: string }
  | { type: 'progress'; status: 'finished'; tool: string; call_id: string; ok: boolean; summary: string }
  | { type: 'progress'; status: 'checking' }
  | {
      type: 'result'
      conversation_id: string
      plan_id: string
      reply: string
      data: ToolResult[]
      issues: string[]
      usage: Usage
    }
  | { type: 'error'; message: string }

export type FlightOption = {
  airline: string
  price_usd: number
  departure_time: string
  arrival_time: string
  stops: number
  duration: string
  notes?: string
  source_url?: string
  longest_layover_minutes?: number
}

export type HotelOption = {
  name: string
  area?: string
  price_per_night_usd: number
  total_usd?: number | null
  rating?: number | null
  reviews?: number | null
  notes?: string
  source_url?: string
}

export type ActivityOption = {
  name: string
  category?: string
  estimated_cost_usd?: number
  duration_hours?: number
  notes?: string
  source_url?: string
}

// Specialist results either come wrapped ({source, warning?, options}) or as a plain list.
export type Sourced<T> = { source?: string; source_url?: string; warning?: string; error?: string; options?: T[] }
