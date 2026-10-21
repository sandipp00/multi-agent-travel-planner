"""Hotel-search specialist agent."""

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

HOTEL_SYSTEM = """You are a hotel-search specialist agent inside a larger travel-planning \
system. Your only job is to read the web search results you are given and report realistic, \
current lodging options for the requested destination and dates as a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 lodging options, each shaped as:
{"name": "...", "area": "...", "price_per_night_usd": <number>, "rating": <number>, "notes": "..."}

Base prices on the search results where they give them. If the results lack real current \
data, provide clearly-labeled realistic estimates in the same schema and note that in "notes"."""

TOOL = {
    "type": "function",
    "function": {
        "name": "search_hotels",
        "description": "Search for hotel/lodging options in a destination using live web search.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "City or area to search for lodging in."},
                "checkin": {"type": "string", "description": "Check-in date, formatted YYYY-MM-DD."},
                "checkout": {"type": "string", "description": "Check-out date, formatted YYYY-MM-DD."},
                "budget_per_night_usd": {
                    "type": ["string", "null"],
                    "description": "Optional target nightly budget in USD, as a string.",
                },
            },
            "required": ["destination", "checkin", "checkout"],
        },
    },
}


def search_hotels(destination: str, checkin: str, checkout: str, budget_per_night_usd: str = ""):
    client = get_client()
    user_message = f"Find lodging options in {destination}, check-in {checkin}, check-out {checkout}."
    if budget_per_night_usd:
        user_message += f" Target roughly ${budget_per_night_usd} per night."
    search_query = f"hotels in {destination} price per night"

    text = call_with_web_search(
        client, HOTEL_SYSTEM, user_message, MODEL_AGENT,
        search_query=search_query, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)
