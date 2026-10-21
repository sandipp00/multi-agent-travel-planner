"""The orchestrator agent: coordinates the flight, hotel, activity,
destination-info, and budget specialist agents (via Groq tool calling) to plan a trip.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from src import fact_check
from src.agents import activity_agent, budget_agent, destination_agent, flight_agent, hotel_agent
from src.config import MAX_TOOL_ROUNDS, MODEL_ORCHESTRATOR, ORCHESTRATOR_MAX_TOKENS

ORCHESTRATOR_SYSTEM = """You are a travel-planning orchestrator. You do not search the web \
yourself — instead you coordinate five specialist agents, each exposed to you as a tool:

- search_flights: a flight-search specialist with live web access
- search_hotels: a lodging-search specialist with live web access
- search_activities: a local-activities specialist with live web access
- get_destination_info: real weather, currency/exchange rate, famous sights, and a travel-guide \
intro for the destination
- analyze_budget: a pure arithmetic specialist that checks cost estimates against budget

For any trip-planning request:
1. Make sure you have origin, destination, dates, and a total budget. Ask the user for \
anything missing before calling tools.
2. Call search_flights, search_hotels, search_activities, and get_destination_info ALL \
TOGETHER in one turn — they are independent and run in parallel, which is much faster. Never \
call the same tool again with the same inputs; reuse the result you already have.
3. Once you have concrete price estimates, call analyze_budget with real numbers drawn from \
the specialists' results — never invent your own totals. When the chosen hotel has a \
total_usd, pass it as hotel_total_usd. Every total, subtotal, and \
remaining amount you show must be copied exactly from analyze_budget's result; if you change \
the selection afterwards, call analyze_budget again.
4. Present the traveler a clear day-by-day itinerary plus a budget summary, citing the \
specific flight/hotel/activity options the specialists found. If analyze_budget reports \
over_budget, say so plainly and suggest concrete cheaper alternatives from the same results.
5. Use get_destination_info in the plan: say what weather to expect (and whether it is a \
forecast or a typical-weather guide), what to pack for it, the local currency with a \
conversion example, and work its famous sights into the itinerary.
6. Choose flights on price AND total trip time, not price alone. Compare each option's \
total_trip_minutes and longest_layover_minutes: prefer a modestly pricier flight that saves \
many hours or avoids a long/overnight layover, and state the trade-off (e.g. "$91 more, \
saves 12 hours"). Plan the arrival day around the actual arrival date and time.

Ground every price and recommendation in a specialist tool's output — never fabricate one. \
Label itinerary days by date only (e.g. "Day 1 – Sep 7"); never name weekdays, since you \
can't compute them reliably. Pass 3-letter IATA airport codes to search_flights, and never \
state return flight times it doesn't give. If a tool result includes a "warning", repeat it \
to the traveler plainly. You cannot book, reserve, or \
hold anything — never offer to; tell the traveler to book through the airline or hotel."""

_AGENTS = {
    "search_flights": flight_agent.search_flights,
    "search_hotels": hotel_agent.search_hotels,
    "search_activities": activity_agent.search_activities,
    "get_destination_info": destination_agent.get_destination_info,
    "analyze_budget": budget_agent.analyze_budget,
}

TOOLS = [
    flight_agent.TOOL, hotel_agent.TOOL, activity_agent.TOOL, destination_agent.TOOL, budget_agent.TOOL,
]


def _run_tool(tool_call) -> str:
    """Run one specialist for a tool call and return its result as JSON.

    Errors come back to the orchestrator as {"error": ...} rather than
    raising, so one failed search doesn't end the whole turn.
    """
    name = tool_call.function.name
    agent = _AGENTS.get(name)
    if agent is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        args = json.loads(tool_call.function.arguments or "{}")
        # Models often send null for optional parameters — drop those so
        # each agent's own default applies.
        args = {key: value for key, value in args.items() if value is not None}
        return json.dumps(agent(**args))
    except Exception as exc:
        return json.dumps({"error": f"{name} failed: {exc}"})


_DUPLICATE_RESULT = json.dumps({
    "_duplicate": True,
    "note": "You already ran this exact search earlier in this plan. Use that earlier result; "
            "don't repeat a search with the same inputs.",
})


def _call_key(tool_call):
    """(tool, canonical arguments) identifying a call, or None if unparseable."""
    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(args, dict):
        return None
    args = {key: value for key, value in args.items() if value is not None}
    return tool_call.function.name, json.dumps(args, sort_keys=True)


def _fact_checked(client, text: str, results: list) -> str:
    """Fix details the model miscopied from the tool data, if any.

    One editing pass; the revision is kept only if it has fewer mismatches.
    Whatever remains is shown to the traveler by the CLI.
    """
    if not results:
        return text
    issues = fact_check.check(text, results)
    if not issues:
        return text
    try:
        revised = fact_check.revise(client, text, issues)
    except Exception:
        return text
    return revised if len(fact_check.check(revised, results)) < len(issues) else text


def _no_event(event: dict) -> None:
    pass


def run_turn(client, messages: list, on_event=_no_event) -> str:
    """Run one full orchestrator turn (including any tool delegation) and
    return the assistant's final text. Appends the assistant and tool
    messages to `messages` in place so the caller can continue the
    conversation.

    `on_event` receives progress dicts as the turn runs — {"type":
    "tool_started"|"tool_finished", "tool", "call_id", ("result")} and
    {"type": "fact_checking"} — so a UI can show agents working. It may be
    called from worker threads.
    """
    turn_start = len(messages)
    seen = set()  # (tool, arguments) already run this turn
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL_ORCHESTRATOR,
            max_tokens=ORCHESTRATOR_MAX_TOKENS,
            messages=[{"role": "system", "content": ORCHESTRATOR_SYSTEM}, *messages],
            tools=TOOLS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            results = tool_results(messages, turn_start)
            if results:
                on_event({"type": "fact_checking"})
            text = _fact_checked(client, message.content or "", results)
            messages.append({"role": "assistant", "content": text})
            return text

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in message.tool_calls
            ],
        })

        def run_and_report(call):
            on_event({"type": "tool_started", "tool": call.function.name, "call_id": call.id})
            result = _run_tool(call)
            on_event({"type": "tool_finished", "tool": call.function.name, "call_id": call.id,
                      "result": json.loads(result)})
            return result

        # The model sometimes repeats a search it already made (same tool,
        # same arguments). Run each distinct call once; point repeats at the
        # earlier result instead of spending another search and more tokens.
        keys = [_call_key(call) for call in message.tool_calls]
        fresh, queued = [], set()
        for call, key in zip(message.tool_calls, keys):
            if key is None or (key not in seen and key not in queued):
                fresh.append(call)
                if key is not None:
                    queued.add(key)

        # Independent specialist calls in one round run in parallel.
        with ThreadPoolExecutor() as pool:
            outputs = dict(zip((call.id for call in fresh), pool.map(run_and_report, fresh)))
        for call, key in zip(message.tool_calls, keys):
            if call.id in outputs:
                result = outputs[call.id]
                if key is not None:
                    seen.add(key)
            else:
                result = _DUPLICATE_RESULT
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "The planner hit its tool-call limit before finishing. Please try rephrasing the request."


def tool_results(messages: list, start: int = 0) -> list:
    """Return (tool name, arguments, result) for every specialist call in
    `messages[start:]`, in call order — the raw data a plan was built from.
    """
    calls = {}
    results = []
    for message in messages[start:]:
        for call in message.get("tool_calls", []):
            calls[call["id"]] = call["function"]
        if message["role"] == "tool" and message["tool_call_id"] in calls:
            function = calls[message["tool_call_id"]]
            result = json.loads(message["content"])
            # A repeated search just points back at the earlier result.
            if isinstance(result, dict) and result.get("_duplicate"):
                continue
            try:
                args = json.loads(function["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            results.append((function["name"], args, result))
    return results
