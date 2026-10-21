# 🧳 Multi-Agent Travel Planner

A trip-planning assistant built as a genuine multi-agent system that runs
**entirely free**: open models on Groq's free tier plus DuckDuckGo web
search (no key needed). One **orchestrator** agent delegates to five
**specialist agents** — some are their own model calls, others pull exact
data from free public APIs.

## Architecture

```
                        ┌─────────────────────────┐
   User ── message ──▶  │  Orchestrator (GPT-OSS)  │
                        │  plans, delegates, and   │
                        │  synthesizes a final     │
                        │  itinerary + budget      │
                        └───────────┬─────────────┘
                                    │ tool calls (Groq function calling)
       ┌──────────────┬─────────────┼───────────────┬────────────────┐
       ▼              ▼             ▼               ▼                ▼
 search_flights  search_hotels  search_activities  get_destination_  analyze_budget
 (Google Flights (Google Hotels (own model call    info              (pure Python —
  fares; web      via SerpApi;   + web search)     (free APIs — no   no LLM call)
  search fallback) web search                       LLM call)
                   fallback)
```

The activity specialist is a **separate model call** (GPT-OSS 20B) with a
narrow system prompt, grounded in its own fresh DuckDuckGo search — not just
a Python function the orchestrator happens to run locally. The hotel
specialist gets **real Google Hotels prices** through
[SerpApi](https://serpapi.com/google-hotels-api) when you add a free
`SERPAPI_API_KEY`, and otherwise makes the same kind of search-and-summarize
model call, flagged as estimates. The flight specialist gets **real fares from Google Flights**
through the free, unofficial [`fast-flights`](https://pypi.org/project/fast-flights/)
library, and falls back to the same search-and-summarize call if Google
Flights is unavailable or it's given a city name instead of an airport code.
`get_destination_info` makes no model call: it gathers real facts from free,
key-less public APIs —

| Data | Source |
|---|---|
| Location | OpenStreetMap Nominatim |
| Weather | Open-Meteo — a forecast when the trip is within ~2 weeks, otherwise the actual weather on the same dates last year as a typical-weather guide |
| Currency | `babel` (country → currency) + ExchangeRate-API (open.er-api.com) |
| Famous sights | Wikidata, ranked by how many Wikipedia languages cover each place |
| Travel guide | Wikivoyage |

Each of those parts fails independently, so one service being down doesn't
lose the rest. The orchestrator never searches the web itself; it only sees
each specialist's structured JSON result and reasons over those.
`analyze_budget` is deliberately plain arithmetic (no LLM call) so budget
checks are exact rather than estimated.

Delegation uses Groq's OpenAI-compatible **function calling**.
`src/orchestrator.py` runs the agentic loop itself: it calls the model,
runs any requested specialists (in parallel when there are several), feeds
their results back, and repeats until the orchestrator answers — capped at
`MAX_TOOL_ROUNDS` so it can't loop forever.

## Project structure

```
multi-agent-travel-planner/
├── cli.py                     # Interactive REPL entry point
├── src/
│   ├── config.py              # Model IDs, token and search limits
│   ├── llm_client.py          # Groq client + DuckDuckGo search-then-summarize
│   ├── json_utils.py          # Lenient JSON extraction from agent replies
│   ├── orchestrator.py        # Orchestrator system prompt + tool wiring
│   ├── report.py              # "Data used for this plan" section
│   ├── fact_check.py          # Checks the plan against the data, fixes mismatches
│   └── agents/
│       ├── flight_agent.py    # Google Flights fares, web-search fallback
│       ├── hotel_agent.py     # Google Hotels via SerpApi, web-search fallback
│       ├── activity_agent.py  # Activities specialist (web search)
│       ├── destination_agent.py # Weather, currency, sights, guide (free APIs)
│       └── budget_agent.py    # Pure-arithmetic budget checker
├── server/                    # Website backend (FastAPI)
│   ├── app.py                 # API: login check, streaming plans, limits, feedback, admin
│   ├── auth.py                # Verifies Supabase login tokens
│   ├── store.py               # Conversations, plans, feedback in Supabase Postgres
│   ├── progress.py            # One-line agent summaries for live progress
│   └── schema.sql             # Database tables — run once in Supabase
├── web/                       # Website frontend (React + Vite + TypeScript)
│   └── src/                   # Login/sign-up, planner chat, data cards, admin page
├── tests/                     # Mocked unit tests — no network/API calls
├── .github/workflows/ci.yml
├── requirements.txt
└── LICENSE
```

## Getting started

```bash
git clone <your-fork-url>
cd multi-agent-travel-planner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Set up credentials

Create a free Groq API key at <https://console.groq.com/keys> (no credit
card needed), then:

```bash
cp .env.example .env   # then fill in GROQ_API_KEY
```

Web search uses DuckDuckGo and needs no key.

**Optional — real hotel prices:** create a free account at
<https://serpapi.com> and add `SERPAPI_API_KEY` to `.env`. Each trip plan
uses one hotel search out of the free plan's monthly allowance. Without the
key, hotel prices are web-search estimates and every plan says so.

The free tier has per-minute and per-day rate limits; a full trip plan uses
several requests, so if you hit a limit, wait a minute and try again. The
orchestrator model's daily allowance (200,000 tokens at the time of
writing) covers roughly 8–10 full plans a day. If
Groq retires a model, set `GROQ_ORCHESTRATOR_MODEL` / `GROQ_AGENT_MODEL` in
`.env` to a current one from <https://console.groq.com/docs/models>.

### Run it

```bash
python cli.py
```

```
You: Plan a 5-day trip from Chicago to Lisbon in September, budget $2500 total.
```

The orchestrator will ask for anything it's missing, then call the flight,
hotel, activity, and destination-info specialists, check the results against
your budget with `analyze_budget`, and present a day-by-day itinerary with
the expected weather, packing tips, local currency, and famous sights.

Under each plan, the CLI prints a **"Data used for this plan"** section
straight from the specialists' results (not rewritten by the model): every
flight, hotel, and activity option with its price and source link, the
weather, exchange rate, and sights with their sources, the budget
arithmetic, and any warning (e.g. flight prices that are estimates
because fares for those dates aren't published yet).

Before showing a plan, `src/fact_check.py` compares it line by line with
that data — catching a price paired with the wrong airline or hotel, a
figure just off the real one (a rounded $75 for a $76 total), or a layover
length that doesn't exist. If it finds any, a quick editing pass fixes just
those; anything still wrong is listed under the plan as **FACT CHECK**.

### Run the tests

```bash
pytest -v
```

All tests mock the Groq client and web search — no API key or network
access is needed to run the suite (see `tests/`).

## Run the website locally

The website adds accounts (email + password, or Google), live agent
progress, data cards, saved trips, feedback, and an admin page. Logins and
data live in a free [Supabase](https://supabase.com) project.

### 1. Set up Supabase (once)

1. Create a free project at <https://supabase.com>.
2. **SQL Editor → New query**, paste the contents of `server/schema.sql`,
   and click **Run**. This creates the tables.
3. **Project Settings → API Keys**: copy the **Project URL**, the
   **publishable** key, and the **secret** key into `.env` as
   `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY`.
   Never share or commit the secret key.
4. **Authentication → URL Configuration**: set **Site URL** to
   `http://localhost:5173` and add `http://localhost:5173/**` under
   **Redirect URLs** (used by confirmation, password-reset, and Google links).
5. Put your own email in `ADMIN_EMAILS` in `.env` to see the admin page.

Email sign-up works now. Supabase's built-in email sender only allows a few
emails per hour — fine for testing; set up custom SMTP in Supabase before a
larger launch.

**Optional — "Continue with Google":** in Google Cloud Console create an
OAuth client (type *Web application*) with the authorized redirect URI
`https://<your-project>.supabase.co/auth/v1/callback`, then paste its client
ID and secret into Supabase → **Authentication → Sign In / Providers →
Google** and enable it.

### 2. Start it

```bash
pip install -r requirements.txt
cd web && npm install && cd ..

# Terminal 1 — backend on :8000
uvicorn server.app:app --reload --port 8000

# Terminal 2 — website on :5173 (forwards /api to the backend)
cd web && npm run dev
```

Open <http://localhost:5173>, sign up, confirm your email, and plan a trip.
Each account gets 3 plans a day and the whole site 8 (the free Groq
allowance); change these with the `PLANS_PER_*` settings in `.env`.

To try the production build on one port: `cd web && npm run build`, then
open <http://localhost:8000> (the backend serves `web/dist`).

## Why this counts as "multi-agent"

- **Independent contexts.** Each specialist gets its own system prompt,
  conversation, and tool set — it has no visibility into the orchestrator's
  reasoning or the other specialists' results.
- **Real delegation.** The hotel and activity specialists (and the flight
  fallback) each make their own `client.chat.completions.create()` call;
  the orchestrator is coordinating separate agent runs.
- **Heterogeneous specialization.** Some agents summarize live web search
  with scoped prompts, some pull exact data from public APIs (Google
  Flights, weather, currency, Wikidata), and one does deterministic math —
  the orchestrator picks the right tool for each kind of sub-problem.

## Tech stack

Python · Groq API (free tier, `openai/gpt-oss-120b` + `openai/gpt-oss-20b`,
function calling) · Google Flights (`fast-flights`) · Google Hotels
(SerpApi, optional) · DuckDuckGo search
(`ddgs`) · Open-Meteo · Wikidata · Wikivoyage · OpenStreetMap Nominatim ·
ExchangeRate-API · pytest · GitHub Actions

## License

[MIT](LICENSE)
