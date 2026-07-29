"""The orchestrator agent: coordinates the flight, hotel, activity, and
budget specialist agents (via the Anthropic tool runner) to plan a trip.
"""

from src.agents.activity_agent import search_activities
from src.agents.budget_agent import analyze_budget
from src.agents.flight_agent import search_flights
from src.agents.hotel_agent import search_hotels
from src.config import MODEL_ORCHESTRATOR, ORCHESTRATOR_MAX_TOKENS

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

Ground every price and recommendation in a specialist tool's output — never fabricate one."""

TOOLS = [search_flights, search_hotels, search_activities, analyze_budget]


def build_runner(client, messages):
    """Create a tool-runner for one orchestrator turn over the given history."""
    return client.beta.messages.tool_runner(
        model=MODEL_ORCHESTRATOR,
        max_tokens=ORCHESTRATOR_MAX_TOKENS,
        system=ORCHESTRATOR_SYSTEM,
        tools=TOOLS,
        messages=messages,
    )


def run_turn(client, messages: list) -> str:
    """Run one full orchestrator turn (including any tool delegation) and
    return the assistant's final text. Appends the assistant turn to
    `messages` in place so the caller can continue the conversation.
    """
    runner = build_runner(client, messages)
    final_message = None
    for message in runner:
        final_message = message

    if final_message is None:
        return ""

    messages.append({"role": "assistant", "content": final_message.content})

    if final_message.stop_reason == "refusal":
        return "The planner declined to continue with this request."

    return "".join(block.text for block in final_message.content if block.type == "text")
