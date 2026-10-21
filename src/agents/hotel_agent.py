"""Hotel-search specialist agent.

Gets real nightly prices from Google Hotels through SerpApi when a free
SERPAPI_API_KEY is set (https://serpapi.com — a limited number of free
searches per month). Without a key, or if SerpApi fails, it falls back to
its own model call grounded in a fresh web search, flagged as estimates.
"""

import os

import httpx

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

HOTEL_SYSTEM = """You are a hotel-search specialist agent inside a larger travel-planning \
system. Your only job is to read the web search results you are given and report realistic, \
current lodging options for the requested destination and dates as a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 lodging options, each shaped as:
{"name": "...", "area": "...", "price_per_night_usd": <number>, "rating": <number>, "notes": "...", \
"source_url": "..."}

Set "source_url" to the URL of the search result the option came from, or "" if it is \
an estimate.

Base prices on the search results where they give them. If the results lack real current \
data, provide clearly-labeled realistic estimates in the same schema and note that in "notes"."""

TOOL = {
    "type": "function",
    "function": {
        "name": "search_hotels",
        "description": (
            "Search for hotel/lodging options in a destination. Uses real Google Hotels prices "
            "when available, otherwise falls back to web-search estimates."
        ),
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

SERPAPI_URL = "https://serpapi.com/search"
MAX_OPTIONS = 5
TIMEOUT_SECONDS = 30
# With a nightly budget, also show places up to this much above it.
BUDGET_HEADROOM = 1.25


def _to_option(prop: dict) -> dict | None:
    nightly = (prop.get("rate_per_night") or {}).get("extracted_lowest")
    if nightly is None:
        return None
    total = (prop.get("total_rate") or {}).get("extracted_lowest")
    notes = "Real price from Google Hotels (via SerpApi), lowest nightly rate across booking sites."
    if total is not None:
        notes += f" Total for the stay: ${total:,.0f} (may include taxes/fees)."
    return {
        "name": prop.get("name", "?"),
        "area": prop.get("hotel_class") or prop.get("type") or "",
        "price_per_night_usd": nightly,
        "total_usd": total,
        "rating": round(prop["overall_rating"], 1) if prop.get("overall_rating") is not None else None,
        "reviews": prop.get("reviews"),
        "notes": notes,
        "source_url": prop.get("link", ""),
    }


def _google_hotels(destination: str, checkin: str, checkout: str, budget_per_night_usd: str):
    """Return (options, None) from SerpApi, or ([], reason) when unavailable."""
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return [], "no SERPAPI_API_KEY is set, so real hotel prices are unavailable"

    params = {
        "engine": "google_hotels",
        "q": f"hotels in {destination}",
        "check_in_date": checkin,
        "check_out_date": checkout,
        "adults": 1,
        "currency": "USD",
        "gl": "us",
        "hl": "en",
        "api_key": api_key,
    }
    try:
        if budget_per_night_usd:
            params["max_price"] = int(float(budget_per_night_usd) * BUDGET_HEADROOM)
    except ValueError:
        pass

    try:
        response = httpx.get(SERPAPI_URL, params=params, timeout=TIMEOUT_SECONDS)
        data = response.json()
    except Exception as exc:
        # Never echo the request URL: it contains the API key.
        return [], f"SerpApi request failed ({type(exc).__name__})"
    if data.get("error"):
        return [], f"SerpApi returned an error: {data['error']}"

    options = [opt for opt in map(_to_option, data.get("properties", [])) if opt]
    options.sort(key=lambda opt: opt["price_per_night_usd"])
    if not options:
        return [], "Google Hotels returned no priced results for this search"
    return options[:MAX_OPTIONS], None


def search_hotels(destination: str, checkin: str, checkout: str, budget_per_night_usd: str = ""):
    options, reason = _google_hotels(destination, checkin, checkout, budget_per_night_usd)
    if options:
        return {"source": "Google Hotels via SerpApi (real prices)", "options": options}

    client = get_client()
    user_message = f"Find lodging options in {destination}, check-in {checkin}, check-out {checkout}."
    if budget_per_night_usd:
        user_message += f" Target roughly ${budget_per_night_usd} per night."
    search_query = f"hotels in {destination} price per night"

    text = call_with_web_search(
        client, HOTEL_SYSTEM, user_message, MODEL_AGENT,
        search_query=search_query, max_tokens=AGENT_MAX_TOKENS,
    )
    return {
        "source": "web search estimates",
        "warning": (
            f"ESTIMATES ONLY — {reason}. These hotel prices come from web search snippets and may "
            "be far from real prices. Tell the traveler the hotel cost is a rough estimate."
        ),
        "options": parse_json_loose(text),
    }
