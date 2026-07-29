# 🧳 Multi-Agent Travel Planner

A trip-planning assistant built as a genuine multi-agent system on the
Claude API: one **orchestrator** agent delegates to four **specialist
agents**, each of which is its own independent Claude call.

## Architecture

```
                        ┌─────────────────────────┐
   User ── message ──▶  │   Orchestrator (Opus 5)  │
                        │  plans, delegates, and   │
                        │  synthesizes a final     │
                        │  itinerary + budget      │
                        └───────────┬─────────────┘
                                    │ tool calls (Anthropic tool runner)
              ┌─────────────┬───────┼────────────┬──────────────┐
              ▼             ▼                    ▼              ▼
      search_flights  search_hotels     search_activities  analyze_budget
      (own Claude call (own Claude call  (own Claude call    (pure Python —
       + web_search)    + web_search)     + web_search)       no LLM call)
```

Each specialist agent is a **separate Claude API call** with a narrow system
prompt and its own `web_search` tool — not just a Python function the
orchestrator happens to run locally. The orchestrator never searches the web
itself; it only sees each specialist's structured JSON result and reasons
over those. `analyze_budget` is deliberately plain arithmetic (no LLM call)
so budget checks are exact rather than estimated.

Delegation is wired through the Anthropic SDK's **tool runner**
(`client.beta.messages.tool_runner`) using the `@beta_tool` decorator — the
runner handles the agentic loop (calling tools, feeding results back,
looping until the orchestrator is done) so `src/orchestrator.py` only
defines *what* the tools are, not the loop itself.

## Project structure

```
multi-agent-travel-planner/
├── cli.py                     # Interactive REPL entry point
├── src/
│   ├── config.py              # Model IDs, effort levels, token limits
│   ├── llm_client.py          # Shared client + web_search call pattern
│   ├── json_utils.py          # Lenient JSON extraction from agent replies
│   ├── orchestrator.py        # Orchestrator system prompt + tool wiring
│   └── agents/
│       ├── flight_agent.py    # Flight-search specialist (web_search)
│       ├── hotel_agent.py     # Lodging-search specialist (web_search)
│       ├── activity_agent.py  # Activities specialist (web_search)
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

Either export an API key:

```bash
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

or run `ant auth login` and leave `.env` empty — the SDK picks up the
resulting profile automatically.

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

All tests mock the Anthropic client — no API key or network access is
needed to run the suite (see `tests/`).

## Why this counts as "multi-agent"

- **Independent contexts.** Each specialist gets its own system prompt,
  conversation, and tool set — it has no visibility into the orchestrator's
  reasoning or the other specialists' results.
- **Real delegation, not function calls dressed up.** Every specialist tool
  makes its own `client.messages.create()` call to Claude; the orchestrator
  is coordinating separate agent runs, not just invoking library code.
- **Heterogeneous specialization.** Three agents search the live web with
  different scoped prompts; the fourth does deterministic math — the
  orchestrator picks the right tool for each kind of sub-problem.

## Tech stack

Python · Anthropic API (`claude-opus-5`, tool runner, `web_search` server
tool) · pytest · GitHub Actions

## License

[MIT](LICENSE)
