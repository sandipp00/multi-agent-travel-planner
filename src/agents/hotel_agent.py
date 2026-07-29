"""Hotel-search specialist agent."""

from anthropic import beta_tool

from src.config import AGENT_EFFORT, AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

HOTEL_SYSTEM = """You are a hotel-search specialist agent inside a larger travel-planning \
system. Your only job is to search the web for realistic, current lodging options for the \
requested destination and dates, then report back a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 lodging options, each shaped as:
{"name": "...", "area": "...", "price_per_night_usd": <number>, "rating": <number>, "notes": "..."}

If you cannot find real current data, provide clearly-labeled realistic estimates in the \
same schema and note that in "notes"."""


def _search_hotels_impl(destination: str, checkin: str, checkout: str, budget_per_night_usd: str = ""):
    client = get_client()
    user_message = f"Find lodging options in {destination}, check-in {checkin}, check-out {checkout}."
    if budget_per_night_usd:
        user_message += f" Target roughly ${budget_per_night_usd} per night."
    user_message += " Search the web for current pricing and availability."

    text = call_with_web_search(
        client, HOTEL_SYSTEM, user_message, MODEL_AGENT,
        effort=AGENT_EFFORT, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)


@beta_tool
def search_hotels(destination: str, checkin: str, checkout: str, budget_per_night_usd: str = "") -> dict:
    """Search for hotel/lodging options in a destination using live web search.

    Args:
        destination: City or area to search for lodging in.
        checkin: Check-in date, formatted YYYY-MM-DD.
        checkout: Check-out date, formatted YYYY-MM-DD.
        budget_per_night_usd: Optional target nightly budget in USD, as a string.
    """
    return _search_hotels_impl(destination, checkin, checkout, budget_per_night_usd)
