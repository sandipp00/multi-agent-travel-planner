"""Activities / itinerary-ideas specialist agent."""

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

ACTIVITY_SYSTEM = """You are a local-activities specialist agent inside a larger \
travel-planning system. Your only job is to read the web search results you are given and \
report well-regarded, currently operating things to do at the requested destination that fit \
the traveler's interests, as a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 4-8 activity options, each shaped as:
{"name": "...", "category": "...", "estimated_cost_usd": <number>, "duration_hours": <number>, "notes": "..."}

If the results lack real current data, provide clearly-labeled realistic estimates in the \
same schema and note that in "notes"."""

TOOL = {
    "type": "function",
    "function": {
        "name": "search_activities",
        "description": "Search for things to do at a destination using live web search.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "City or area to search for activities in."},
                "start_date": {"type": "string", "description": "Trip start date, formatted YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "Trip end date, formatted YYYY-MM-DD."},
                "interests": {
                    "type": ["string", "null"],
                    "description": 'Optional comma-separated interests (e.g. "hiking, museums, food").',
                },
            },
            "required": ["destination", "start_date", "end_date"],
        },
    },
}


def search_activities(destination: str, start_date: str, end_date: str, interests: str = ""):
    client = get_client()
    user_message = f"Find things to do in {destination} between {start_date} and {end_date}."
    if interests:
        user_message += f" The traveler is interested in: {interests}."
    search_query = f"best things to do in {destination} {interests}".strip()

    text = call_with_web_search(
        client, ACTIVITY_SYSTEM, user_message, MODEL_AGENT,
        search_query=search_query, max_tokens=AGENT_MAX_TOKENS,
    )
    return parse_json_loose(text)
