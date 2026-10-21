"""The orchestrator agent: coordinates the flight, hotel, activity, and
budget specialist agents (via Groq tool calling) to plan a trip.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from src.agents import activity_agent, budget_agent, flight_agent, hotel_agent
from src.config import MAX_TOOL_ROUNDS, MODEL_ORCHESTRATOR, ORCHESTRATOR_MAX_TOKENS

ORCHESTRATOR_SYSTEM = """You are a travel-planning orchestrator. You do not search the web \
yourself — instead you coordinate four specialist agents, each exposed to you as a tool:

- search_flights: a flight-search specialist with live web access
- search_hotels: a lodging-search specialist with live web access
- search_activities: a local-activities specialist with live web access
- analyze_budget: a pure arithmetic specialist that checks cost estimates against budget

For any trip-planning request:
1. Make sure you have origin, destination, dates, and a total budget. Ask the user for \
anything missing before calling tools.
2. Call search_flights, search_hotels, and search_activities to gather concrete options. \
You may call independent tools in the same turn so they run in parallel.
3. Once you have concrete price estimates, call analyze_budget with real numbers drawn from \
the specialists' results — never invent your own totals.
4. Present the traveler a clear day-by-day itinerary plus a budget summary, citing the \
specific flight/hotel/activity options the specialists found. If analyze_budget reports \
over_budget, say so plainly and suggest concrete cheaper alternatives from the same results.

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
    "analyze_budget": budget_agent.analyze_budget,
}

TOOLS = [flight_agent.TOOL, hotel_agent.TOOL, activity_agent.TOOL, budget_agent.TOOL]


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


def run_turn(client, messages: list) -> str:
    """Run one full orchestrator turn (including any tool delegation) and
    return the assistant's final text. Appends the assistant and tool
    messages to `messages` in place so the caller can continue the
    conversation.
    """
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL_ORCHESTRATOR,
            max_tokens=ORCHESTRATOR_MAX_TOKENS,
            messages=[{"role": "system", "content": ORCHESTRATOR_SYSTEM}, *messages],
            tools=TOOLS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            text = message.content or ""
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

        # Independent specialist calls in one round run in parallel.
        with ThreadPoolExecutor() as pool:
            results = list(pool.map(_run_tool, message.tool_calls))
        for call, result in zip(message.tool_calls, results):
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
            try:
                args = json.loads(function["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            results.append((function["name"], args, json.loads(message["content"])))
    return results
