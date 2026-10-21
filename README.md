# 🧳 Multi-Agent Travel Planner

A trip-planning assistant built as a genuine multi-agent system that runs
**entirely free**: open models on Groq's free tier plus DuckDuckGo web
search (no key needed). One **orchestrator** agent delegates to four
**specialist agents**, each of which is its own independent model call.

## Architecture

```
                        ┌─────────────────────────┐
   User ── message ──▶  │  Orchestrator (GPT-OSS)  │
                        │  plans, delegates, and   │
                        │  synthesizes a final     │
                        │  itinerary + budget      │
                        └───────────┬─────────────┘
                                    │ tool calls (Groq function calling)
              ┌─────────────┬───────┼────────────┬──────────────┐
              ▼             ▼                    ▼              ▼
      search_flights  search_hotels     search_activities  analyze_budget
      (own model call  (own model call   (own model call     (pure Python —
       + web search)    + web search)     + web search)       no LLM call)
```

Each specialist agent is a **separate model call** (GPT-OSS 20B) with a
narrow system prompt, grounded in its own fresh DuckDuckGo search — not just
a Python function the orchestrator happens to run locally. The orchestrator never searches the web
itself; it only sees each specialist's structured JSON result and reasons
over those. `analyze_budget` is deliberately plain arithmetic (no LLM call)
so budget checks are exact rather than estimated.

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
│   └── agents/
│       ├── flight_agent.py    # Flight-search specialist (web search)
│       ├── hotel_agent.py     # Lodging-search specialist (web search)
│       ├── activity_agent.py  # Activities specialist (web search)
│       └── budget_agent.py    # Pure-arithmetic budget checker
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

The free tier has per-minute and per-day rate limits; a full trip plan uses
several requests, so if you hit a limit, wait a minute and try again. If
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
hotel, and activity specialists (each doing its own live web search),
check the results against your budget with `analyze_budget`, and present a
day-by-day itinerary.

### Run the tests

```bash
pytest -v
```

All tests mock the Groq client and web search — no API key or network
access is needed to run the suite (see `tests/`).

## Why this counts as "multi-agent"

- **Independent contexts.** Each specialist gets its own system prompt,
  conversation, and tool set — it has no visibility into the orchestrator's
  reasoning or the other specialists' results.
- **Real delegation, not function calls dressed up.** Every specialist tool
  makes its own `client.chat.completions.create()` call; the orchestrator
  is coordinating separate agent runs, not just invoking library code.
- **Heterogeneous specialization.** Three agents search the live web with
  different scoped prompts; the fourth does deterministic math — the
  orchestrator picks the right tool for each kind of sub-problem.

## Tech stack

Python · Groq API (free tier, `openai/gpt-oss-120b` + `openai/gpt-oss-20b`,
function calling) · DuckDuckGo search (`ddgs`) · pytest · GitHub Actions

## License

[MIT](LICENSE)
