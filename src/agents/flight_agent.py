"""Flight-search specialist agent.

Runs its own Claude call with the web_search tool, scoped to a single
narrow task, and returns a small structured result to the orchestrator.
"""

from anthropic import beta_tool

from src.config import AGENT_EFFORT, AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

FLIGHT_SYSTEM = """You are a flight-search specialist agent inside a larger travel-planning \
system. Your only job is to search the web for realistic, current flight options for the \
requested route and dates, then report back a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 flight options, each shaped as:
{"airline": "...", "price_usd": <number>, "departure_time": "...", "arrival_time": "...", \
"stops": <integer>, "duration": "...", "notes": "..."}

If you cannot find real current data, provide clearly-labeled realistic estimates in the \
same schema and note that in "notes"."""


def _search_flights_impl(origin: str, destination: str, depart_date: str, return_date: str = ""):
    client = get_client()
    trip = f"from {origin} to {destination}, departing {depart_date}"
    trip += f", returning {return_date}" if return_date else " (one-way)"
    user_message = f"Find flight options {trip}. Search the web for current pricing and schedules."

    text = call_with_web_search(
        client, FLIGHT_SYSTEM, user_message, MODEL_AGENT,
        effort=AGENT_EFFORT, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)


@beta_tool
def search_flights(origin: str, destination: str, depart_date: str, return_date: str = "") -> dict:
    """Search for flight options between two cities using live web search.

    Args:
        origin: Departure city or airport.
        destination: Arrival city or airport.
        depart_date: Outbound date, formatted YYYY-MM-DD.
        return_date: Return date, formatted YYYY-MM-DD. Leave empty for a one-way trip.
    """
    return _search_flights_impl(origin, destination, depart_date, return_date)
