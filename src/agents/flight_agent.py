"""Flight-search specialist agent.

Gets real fares from Google Flights (via the free, unofficial fast-flights
library) when given airport codes. If that fails — Google changed its page,
no results, or a city name instead of a code — it falls back to its own
model call grounded in a fresh web search.
"""

import datetime as dt
import re

from fast_flights import FlightQuery, Passengers, create_query, get_flights

from src.config import AGENT_MAX_TOKENS, MODEL_AGENT
from src.json_utils import parse_json_loose
from src.llm_client import call_with_web_search, get_client

FLIGHT_SYSTEM = """You are a flight-search specialist agent inside a larger travel-planning \
system. Your only job is to read the web search results you are given and report realistic, \
current flight options for the requested route and dates as a compact structured summary.

Respond with ONLY a JSON array (no prose, no markdown fences) of 3-5 flight options, each shaped as:
{"airline": "...", "price_usd": <number>, "departure_time": "...", "arrival_time": "...", \
"stops": <integer>, "duration": "...", "notes": "...", \
"source_url": "..."}

Set "source_url" to the URL of the search result the option came from, or "" if it is \
an estimate.

Base prices on the search results where they give them. If the results lack real current \
data, provide clearly-labeled realistic estimates in the same schema and note that in "notes"."""

TOOL = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": (
            "Search for flight options between two airports. Uses real Google Flights fares "
            "when given 3-letter IATA airport codes, otherwise falls back to web search."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": 'Departure airport as a 3-letter IATA code (e.g. "ORD" for Chicago).',
                },
                "destination": {
                    "type": "string",
                    "description": 'Arrival airport as a 3-letter IATA code (e.g. "LIS" for Lisbon).',
                },
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

MAX_OPTIONS = 5
# Google Flights only publishes fares roughly 330 days ahead (measured
# October 2026); later dates always come back empty.
BOOKING_HORIZON_DAYS = 330
_IATA_RE = re.compile(r"^[A-Za-z]{3}$")


def _format_datetime(value) -> str:
    year, month, day = value.date
    hour, minute = (tuple(value.time) + (0, 0))[:2]
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def _to_option(result, round_trip: bool) -> dict:
    legs = result.flights
    stops = len(legs) - 1
    flying_minutes = sum(leg.duration for leg in legs)
    notes = "Real fare from Google Flights"
    notes += (
        " (round-trip total). Outbound times only; return times not available."
    ) if round_trip else " (one-way)."
    if stops:
        notes += " Connects via " + ", ".join(leg.to_airport.code for leg in legs[:-1]) + "."
    return {
        "airline": ", ".join(result.airlines),
        "price_usd": result.price,
        "departure_time": _format_datetime(legs[0].departure),
        "arrival_time": _format_datetime(legs[-1].arrival),
        "stops": stops,
        "duration": f"{flying_minutes // 60}h {flying_minutes % 60}m flying time",
        "notes": notes,
    }


def _google_flights(origin: str, destination: str, depart_date: str, return_date: str):
    """Return (up to MAX_OPTIONS cheapest real fares, Google Flights URL),
    or ([], "") if unavailable.
    """
    if not (_IATA_RE.match(origin) and _IATA_RE.match(destination)):
        return [], ""
    origin, destination = origin.upper(), destination.upper()

    legs = [FlightQuery(date=depart_date, from_airport=origin, to_airport=destination)]
    if return_date:
        legs.append(FlightQuery(date=return_date, from_airport=destination, to_airport=origin))
    query = create_query(
        flights=legs,
        trip="round-trip" if return_date else "one-way",
        passengers=Passengers(adults=1),
        currency="USD",
        language="en-US",
    )

    try:
        results = [r for r in get_flights(query) if r.price and r.flights]
        results.sort(key=lambda r: r.price)
        return [_to_option(r, bool(return_date)) for r in results[:MAX_OPTIONS]], query.url()
    except Exception:
        # Unofficial scraper: any change on Google's side lands here.
        return [], ""


def _fallback_warning(origin: str, destination: str, depart_date: str, return_date: str) -> str:
    horizon = dt.date.today() + dt.timedelta(days=BOOKING_HORIZON_DAYS)
    try:
        latest = max(dt.date.fromisoformat(d) for d in (depart_date, return_date) if d)
    except ValueError:
        latest = None
    if latest and latest > horizon:
        reason = (
            f"airlines haven't published fares for these dates yet (Google Flights only "
            f"lists flights up to about {horizon.isoformat()})"
        )
    elif not (_IATA_RE.match(origin) and _IATA_RE.match(destination)):
        reason = "real fares need 3-letter IATA airport codes, but city names were given"
    else:
        reason = "Google Flights returned no fares for this search"
    return (
        f"ESTIMATES ONLY — {reason}. These options come from web search snippets and may be "
        "far from real prices. Tell the traveler the flight cost is a rough estimate."
    )


def search_flights(origin: str, destination: str, depart_date: str, return_date: str = ""):
    options, url = _google_flights(origin, destination, depart_date, return_date)
    if options:
        return {"source": "Google Flights (real fares)", "source_url": url, "options": options}

    client = get_client()
    trip = f"from {origin} to {destination}, departing {depart_date}"
    trip += f", returning {return_date}" if return_date else " (one-way)"
    user_message = f"Find flight options {trip}."
    search_query = f"flights {origin} to {destination} {depart_date} price"

    text = call_with_web_search(
        client, FLIGHT_SYSTEM, user_message, MODEL_AGENT,
        search_query=search_query, max_tokens=AGENT_MAX_TOKENS,
    )
    return {
        "source": "web search estimates",
        "warning": _fallback_warning(origin, destination, depart_date, return_date),
        "options": parse_json_loose(text),
    }
