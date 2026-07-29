"""Activities / itinerary-ideas specialist agent."""

from anthropic import beta_tool

from src.config import AGENT_EFFORT, AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

ACTIVITY_SYSTEM = """You are a local-activities specialist agent inside a larger \
travel-planning system. Your only job is to search the web for well-regarded, currently \
operating things to do at the requested destination that fit the traveler's interests, then \
report back a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 4-8 activity options, each shaped as:
{"name": "...", "category": "...", "estimated_cost_usd": <number>, "duration_hours": <number>, "notes": "..."}

If you cannot find real current data, provide clearly-labeled realistic estimates in the \
same schema and note that in "notes"."""


def _search_activities_impl(destination: str, start_date: str, end_date: str, interests: str = ""):
    client = get_client()
    user_message = f"Find things to do in {destination} between {start_date} and {end_date}."
    if interests:
        user_message += f" The traveler is interested in: {interests}."
    user_message += " Search the web for current, well-reviewed options."

    text = call_with_web_search(
        client, ACTIVITY_SYSTEM, user_message, MODEL_AGENT,
        effort=AGENT_EFFORT, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)


@beta_tool
def search_activities(destination: str, start_date: str, end_date: str, interests: str = "") -> dict:
    """Search for things to do at a destination using live web search.

    Args:
        destination: City or area to search for activities in.
        start_date: Trip start date, formatted YYYY-MM-DD.
        end_date: Trip end date, formatted YYYY-MM-DD.
        interests: Optional comma-separated interests (e.g. "hiking, museums, food").
    """
    return _search_activities_impl(destination, start_date, end_date, interests)
