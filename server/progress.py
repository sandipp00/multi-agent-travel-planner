"""One-line summaries of each specialist's result, for the live progress list."""

AGENT_LABELS = {
    "search_flights": "Flights",
    "search_hotels": "Hotels",
    "search_activities": "Activities",
    "get_destination_info": "Weather, currency & sights",
    "analyze_budget": "Budget check",
}


def _options(result) -> list:
    if isinstance(result, dict):
        result = result.get("options", [])
    return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []


def _cheapest(options: list, key: str) -> str:
    prices = [o[key] for o in options if isinstance(o.get(key), (int, float))]
    return f" from ${min(prices):,.0f}" if prices else ""


def summarize(tool: str, result) -> tuple[bool, str]:
    """Return (ok, short summary) for one finished specialist."""
    if isinstance(result, dict) and "error" in result:
        return False, "failed — the plan will work around it"
    estimated = isinstance(result, dict) and "warning" in result

    if tool == "search_flights":
        options = _options(result)
        kind = "estimated fares" if estimated else "real fares"
        return True, f"{len(options)} {kind}{_cheapest(options, 'price_usd')}"
    if tool == "search_hotels":
        options = _options(result)
        kind = "estimated hotels" if estimated else "hotels with real prices"
        return True, f"{len(options)} {kind}{_cheapest(options, 'price_per_night_usd')}/night"
    if tool == "search_activities":
        return True, f"{len(_options(result))} ideas"
    if tool == "get_destination_info":
        parts = [name for name in ("weather", "currency", "sights", "guide")
                 if isinstance(result, dict) and not (isinstance(result.get(name), dict) and "error" in result[name])]
        return True, ", ".join(parts) or "no details available"
    if tool == "analyze_budget" and isinstance(result, dict):
        status = "over budget" if result.get("over_budget") else "within budget"
        return True, f"${result.get('total_cost_usd', 0):,.0f} of ${result.get('budget_usd', 0):,.0f} — {status}"
    return True, "done"
