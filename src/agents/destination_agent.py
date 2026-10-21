"""Destination-info specialist agent.

Like the budget agent, this one makes no LLM call: it pulls facts from
free, key-less public APIs so the orchestrator plans around real data
instead of guesses —

- location:  OpenStreetMap Nominatim
- weather:   Open-Meteo (forecast within 16 days, otherwise the same dates
             last year as a "typical weather" guide)
- currency:  babel (country -> currency) + open.er-api.com exchange rates
- sights:    Wikidata (museums, landmarks... ranked by popularity)
- guide:     Wikivoyage intro text

Each part fails independently: one service being down yields an "error"
for that part, not for the whole result.
"""

import datetime as dt

import httpx
from babel.numbers import get_territory_currencies

# Nominatim and Wikidata ask every client to identify itself.
USER_AGENT = "multi-agent-travel-planner/1.0 (+https://github.com/sandipp00/multi-agent-travel-planner)"
TIMEOUT_SECONDS = 30
FORECAST_HORIZON_DAYS = 15
MAX_SIGHTS = 10
SIGHTS_RADIUS_KM = 4
GUIDE_CHARS = 600

TOOL = {
    "type": "function",
    "function": {
        "name": "get_destination_info",
        "description": (
            "Get real facts about a destination for the trip dates: expected weather, local "
            "currency and exchange rate from the traveler's currency, the most famous sights "
            "(from Wikidata), and a short Wikivoyage travel-guide intro."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": 'City name, e.g. "Rome, Italy".'},
                "start_date": {"type": "string", "description": "Trip start date, formatted YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "Trip end date, formatted YYYY-MM-DD."},
                "home_currency": {
                    "type": ["string", "null"],
                    "description": 'Traveler\'s currency as an ISO code (default "USD").',
                },
            },
            "required": ["destination", "start_date", "end_date"],
        },
    },
}


def _get_json(url: str, params: dict | None = None):
    response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _geocode(destination: str) -> dict:
    results = _get_json(
        "https://nominatim.openstreetmap.org/search",
        {"q": destination, "format": "json", "limit": 1, "addressdetails": 1},
    )
    if not results:
        raise ValueError(f"Could not find {destination!r} on OpenStreetMap")
    place = results[0]
    return {
        "name": place.get("display_name", destination),
        "lat": float(place["lat"]),
        "lon": float(place["lon"]),
        "country_code": place.get("address", {}).get("country_code", "").upper(),
    }


def _weather_window(start: dt.date, end: dt.date, today: dt.date):
    """Pick ("forecast", start, end) for trips within the forecast horizon,
    else ("typical", same dates in the most recent past year, ...).
    """
    if start <= today + dt.timedelta(days=FORECAST_HORIZON_DAYS) and end >= today:
        return "forecast", max(start, today), min(end, today + dt.timedelta(days=FORECAST_HORIZON_DAYS))
    years_back = max(1, start.year - today.year)
    while True:
        try:
            past_start = start.replace(year=start.year - years_back)
            past_end = end.replace(year=end.year - years_back)
        except ValueError:  # Feb 29 in a non-leap year
            past_start = start.replace(year=start.year - years_back, day=28)
            past_end = end.replace(year=end.year - years_back, day=min(end.day, 28))
        # The archive lags a few days behind today.
        if past_end < today - dt.timedelta(days=7):
            return "typical", past_start, past_end
        years_back += 1


def _weather(lat: float, lon: float, start: dt.date, end: dt.date) -> dict:
    kind, window_start, window_end = _weather_window(start, end, dt.date.today())
    url = (
        "https://api.open-meteo.com/v1/forecast" if kind == "forecast"
        else "https://archive-api.open-meteo.com/v1/archive"
    )
    daily = _get_json(url, {
        "latitude": lat,
        "longitude": lon,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
    })["daily"]

    highs = [t for t in daily["temperature_2m_max"] if t is not None]
    lows = [t for t in daily["temperature_2m_min"] if t is not None]
    rain = [p for p in daily["precipitation_sum"] if p is not None]
    if not highs or not lows:
        raise ValueError("Open-Meteo returned no temperatures")
    high, low = sum(highs) / len(highs), sum(lows) / len(lows)
    basis = (
        "forecast for the trip dates" if kind == "forecast"
        else f"actual weather on the same dates in {window_start.year} (a typical-weather guide, not a forecast)"
    )
    return {
        "basis": basis,
        "avg_high_c": round(high, 1),
        "avg_low_c": round(low, 1),
        "avg_high_f": round(high * 9 / 5 + 32),
        "avg_low_f": round(low * 9 / 5 + 32),
        "rainy_days": sum(1 for p in rain if p >= 1.0),
        "days": len(highs),
        "source": "Open-Meteo",
    }


def _currency(country_code: str, home_currency: str) -> dict:
    currencies = get_territory_currencies(country_code) if country_code else []
    if not currencies:
        raise ValueError(f"No currency found for country {country_code!r}")
    local = currencies[0]
    if local == home_currency:
        return {"local_currency": local, "home_currency": home_currency, "rate": 1.0}
    data = _get_json(f"https://open.er-api.com/v6/latest/{home_currency}")
    rate = data.get("rates", {}).get(local)
    if rate is None:
        raise ValueError(f"No exchange rate for {home_currency} -> {local}")
    return {
        "local_currency": local,
        "home_currency": home_currency,
        "rate": rate,
        "example": f"100 {home_currency} = {round(100 * rate, 2)} {local}",
        "as_of": data.get("time_last_update_utc", ""),
        "source": "ExchangeRate-API (open.er-api.com)",
    }


# Wikidata classes that count as sights: museum, art museum, open-air museum,
# tourist attraction, archaeological site, palace, castle, fortification,
# cathedral, church building, fountain, square, monument, park, bridge.
_SIGHT_TYPES = (
    "wd:Q33506 wd:Q207694 wd:Q1060829 wd:Q570116 wd:Q839954 wd:Q16560 wd:Q23413 "
    "wd:Q57821 wd:Q2977 wd:Q16970 wd:Q483453 wd:Q174782 wd:Q4989906 wd:Q22698 wd:Q12280"
)


def _sights(lat: float, lon: float) -> list:
    """Notable sights near the destination, most famous first.

    Ranked by how many Wikipedia language editions cover each place — a
    good popularity signal that needs no API key.
    """
    query = f"""
SELECT ?item ?itemLabel ?typeLabel ?sitelinks ?website WHERE {{
  SERVICE wikibase:around {{
    ?item wdt:P625 ?loc .
    bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral ;
                    wikibase:radius "{SIGHTS_RADIUS_KM}" .
  }}
  VALUES ?type {{ {_SIGHT_TYPES} }}
  ?item wdt:P31 ?type ; wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P856 ?website }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
ORDER BY DESC(?sitelinks) LIMIT {MAX_SIGHTS * 3}"""
    rows = _get_json("https://query.wikidata.org/sparql", {"query": query, "format": "json"})
    sights, seen = [], set()
    # A place with several types or websites comes back once per combination.
    for row in rows["results"]["bindings"]:
        item = row["item"]["value"]
        if item in seen:
            continue
        seen.add(item)
        sights.append({
            "name": row["itemLabel"]["value"],
            "type": row["typeLabel"]["value"],
            "website": row.get("website", {}).get("value", ""),
        })
    return sights[:MAX_SIGHTS]


def _guide(destination: str) -> dict:
    title = destination.split(",")[0].strip()
    pages = _get_json("https://en.wikivoyage.org/w/api.php", {
        "action": "query",
        "prop": "extracts",
        "titles": title,
        "explaintext": 1,
        "exintro": 1,
        "redirects": 1,
        "format": "json",
    })["query"]["pages"]
    page = next(iter(pages.values()))
    extract = (page.get("extract") or "").strip()
    if not extract:
        raise ValueError(f"No Wikivoyage article for {title!r}")
    return {
        "summary": extract[:GUIDE_CHARS],
        "url": f"https://en.wikivoyage.org/wiki/{page['title'].replace(' ', '_')}",
        "source": "Wikivoyage",
    }


def _safely(part, *args):
    try:
        return part(*args)
    except Exception as exc:
        return {"error": f"{part.__name__.lstrip('_')} unavailable: {exc}"}


def get_destination_info(destination: str, start_date: str, end_date: str, home_currency: str = "USD") -> dict:
    try:
        place = _geocode(destination)
    except Exception as exc:
        return {"error": f"location lookup failed: {exc}"}

    try:
        start, end = dt.date.fromisoformat(start_date), dt.date.fromisoformat(end_date)
        weather = _safely(_weather, place["lat"], place["lon"], start, end)
    except ValueError as exc:
        weather = {"error": f"weather unavailable: bad dates ({exc})"}

    return {
        "location": place["name"],
        "weather": weather,
        "currency": _safely(_currency, place["country_code"], (home_currency or "USD").upper()),
        "sights": _safely(_sights, place["lat"], place["lon"]),
        "guide": _safely(_guide, destination),
    }
