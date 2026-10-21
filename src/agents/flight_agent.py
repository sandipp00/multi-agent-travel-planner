"""Flight-search specialist agent.

Runs its own model call grounded in a fresh web search, scoped to a single
narrow task, and returns a small structured result to the orchestrator.
"""

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

FLIGHT_SYSTEM = """You are a flight-search specialist agent inside a larger travel-planning \
system. Your only job is to read the web search results you are given and report realistic, \
current flight options for the requested route and dates as a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 flight options, each shaped as:
{"airline": "...", "price_usd": <number>, "departure_time": "...", "arrival_time": "...", \
"stops": <integer>, "duration": "...", "notes": "..."}

Base prices on the search results where they give them. If the results lack real current \
data, provide clearly-labeled realistic estimates in the same schema and note that in "notes"."""

TOOL = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": "Search for flight options between two cities using live web search.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city or airport."},
                "destination": {"type": "string", "description": "Arrival city or airport."},
                "depart_date": {"type": "string", "description": "Outbound date, formatted YYYY-MM-DD."},
                "return_date": {
                    "type": ["string", "null"],
                    "description": "Return date, formatted YYYY-MM-DD. Leave empty for a one-way trip.",
                },
            },
            "required": ["origin", "destination", "depart_date"],
        },
    },
}


def search_flights(origin: str, destination: str, depart_date: str, return_date: str = ""):
    client = get_client()
    trip = f"from {origin} to {destination}, departing {depart_date}"
    trip += f", returning {return_date}" if return_date else " (one-way)"
    user_message = f"Find flight options {trip}."
    search_query = f"flights {origin} to {destination} {depart_date} price"

    text = call_with_web_search(
        client, FLIGHT_SYSTEM, user_message, MODEL_AGENT,
        search_query=search_query, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)
