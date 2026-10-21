import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { AgentProgress } from '../components/AgentProgress'
import { TripForm } from '../components/TripForm'
import { TurnView } from '../components/TurnView'
import { api, ApiError, streamChat } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { ConversationSummary, Me, ProgressStep, Turn } from '../types'

type Pending = { request: string; steps: ProgressStep[]; checking: boolean }

export function PlannerPage() {
  const { supabase } = useAuth()
  const [me, setMe] = useState<Me | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [pending, setPending] = useState<Pending | null>(null)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    try {
      const [nextMe, nextConversations] = await Promise.all([api.me(), api.conversations()])
      setMe(nextMe)
      setConversations(nextConversations)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your account.')
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns, pending])

  async function openConversation(id: string) {
    if (pending) return
    setSidebarOpen(false)
    setError(null)
    try {
      const conversation = await api.conversation(id)
      setActiveId(id)
      setTurns(conversation.turns)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open that trip.')
    }
  }

  function newTrip() {
    if (pending) return
    setActiveId(null)
    setTurns([])
    setError(null)
    setSidebarOpen(false)
  }

  async function send(message: string) {
    const text = message.trim()
    if (!text || pending) return
    setError(null)
    setInput('')
    setPending({ request: text, steps: [], checking: false })
    try {
      await streamChat(text, activeId, (event) => {
        if (event.type === 'progress') {
          setPending((current) => {
            if (!current) return current
            if (event.status === 'checking') return { ...current, checking: true }
            if (event.status === 'started') {
              return { ...current, steps: [...current.steps, { call_id: event.call_id, tool: event.tool, label: event.label, status: 'started' }] }
            }
            return {
              ...current,
              steps: current.steps.map((step) =>
                step.call_id === event.call_id ? { ...step, status: 'finished', ok: event.ok, summary: event.summary } : step),
            }
          })
        } else if (event.type === 'result') {
          setTurns((current) => [...current, {
            plan_id: event.plan_id, request: text, reply: event.reply, data: event.data, issues: event.issues,
            feedback: { rating: null, comment: '', flags: [] },
          }])
          setActiveId(event.conversation_id)
          setMe((current) => (current ? { ...current, usage: event.usage } : current))
        } else if (event.type === 'error') {
          setError(event.message)
          setInput(text)
        }
      })
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Something went wrong.')
      setInput(text)
    } finally {
      setPending(null)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void send(input)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send(input)
    }
  }

  const usage = me?.usage
  const atLimit = !!usage && (usage.plans_today >= usage.plans_limit || usage.site_plans_today >= usage.site_plans_limit)

  return (
    <div className="app-shell">
      <header className="topbar">
        <button type="button" className="icon-button only-mobile" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Your trips">☰</button>
        <div className="brand"><span className="brand-mark" aria-hidden>✈</span> Trip Planner</div>
        <div className="topbar-right">
          {usage && (
            <span className={`usage-pill ${atLimit ? 'full' : ''}`} title="Free plans run on limited AI capacity">
              {usage.plans_today}/{usage.plans_limit} plans today
            </span>
          )}
          {me?.is_admin && <Link to="/admin" className="link small">Admin</Link>}
          <span className="muted small hide-mobile">{me?.email}</span>
          <button type="button" className="button secondary small" onClick={() => void supabase?.auth.signOut()}>Log out</button>
        </div>
      </header>

      <div className="layout">
        <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <button type="button" className="button primary full" onClick={newTrip} disabled={!!pending}>+ New trip</button>
          <h2 className="sidebar-title">Your trips</h2>
          {conversations.length === 0 && <p className="muted small">No trips yet.</p>}
          <ul className="conversation-list">
            {conversations.map((c) => (
              <li key={c.id}>
                <button type="button" className={c.id === activeId ? 'active' : ''} onClick={() => void openConversation(c.id)} disabled={!!pending}>
                  {c.title || 'Untitled trip'}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="chat">
          <div className="thread">
            {turns.length === 0 && !pending && (
              <section className="welcome">
                <h1>Where to next?</h1>
                <p className="muted">
                  Fill in your trip, or just describe it below. A team of agents checks real flight and hotel
                  prices, the weather, currency and top sights, then builds a day-by-day plan within your budget.
                </p>
                <TripForm disabled={atLimit} onSubmit={(message) => void send(message)} />
              </section>
            )}

            {turns.map((turn) => <TurnView key={turn.plan_id} turn={turn} />)}

            {pending && (
              <article className="turn">
                <div className="bubble user">{pending.request}</div>
                <div className="bubble planner"><AgentProgress steps={pending.steps} checking={pending.checking} /></div>
              </article>
            )}
            <div ref={endRef} />
          </div>

          <form className="composer" onSubmit={submit}>
            {error && <p className="alert error" role="alert">{error}</p>}
            <div className="composer-row">
              <textarea
                rows={2}
                maxLength={2000}
                placeholder={turns.length ? 'Ask a follow-up — e.g. “find a cheaper hotel”' : 'Or describe your trip — e.g. “5 days from London (LHR) to Marrakesh, June 3–8, $1500, I like food”'}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                disabled={!!pending || atLimit}
              />
              <button className="button primary" disabled={!!pending || !input.trim() || atLimit}>
                {pending ? 'Planning…' : 'Send'}
              </button>
            </div>
            {atLimit && <p className="muted small">You’ve reached today’s free limit — come back tomorrow.</p>}
          </form>
        </main>
      </div>
    </div>
  )
}
