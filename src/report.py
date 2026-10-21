"""Plain-text report of the data the specialist agents returned.

Printed under each plan straight from the tool results — not rewritten by
the model — so every price and source in the plan can be checked.
"""


def _money(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "?"


def _link(item: dict) -> str:
    url = item.get("source_url") or ""
    return f"\n      {url}" if url else "\n      (no source link — estimate)"


def _options(result):
    """Normalize a specialist result to (options, header lines)."""
    header = []
    if isinstance(result, dict):
        if "error" in result:
            return [], [f"  Error: {result['error']}"]
        if "raw" in result:
            return [], ["  Agent reply was not valid JSON:", f"  {str(result['raw'])[:300]}"]
        if "source" in result:
            header.append(f"  Source: {result['source']}")
        if result.get("source_url"):
            header.append(f"  Link: {result['source_url']}")
        if result.get("warning"):
            header.append(f"  Warning: {result['warning']}")
        result = result.get("options", [])
    options = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    return options, header


def _flight_lines(result) -> list:
    options, lines = _options(result)
    for item in options:
        stops = item.get("stops")
        stop_text = "nonstop" if stops == 0 else f"{stops} stop(s)" if stops is not None else ""
        lines.append(
            f"  - {item.get('airline', '?')}: {_money(item.get('price_usd'))}, "
            f"{item.get('departure_time', '?')} -> {item.get('arrival_time', '?')}, "
            f"{stop_text}, {item.get('duration', '')}"
        )
        if item.get("notes"):
            lines.append(f"      {item['notes']}")
        # Google Flights options share the one link printed in the header.
        if "source_url" in item:
            lines[-1] += _link(item)
    return lines


def _hotel_lines(result) -> list:
    options, lines = _options(result)
    for item in options:
        lines.append(
            f"  - {item.get('name', '?')} ({item.get('area', '?')}): "
            f"{_money(item.get('price_per_night_usd'))}/night, rating {item.get('rating', '?')}"
            + _link(item)
        )
    return lines


def _activity_lines(result) -> list:
    options, lines = _options(result)
    for item in options:
        lines.append(
            f"  - {item.get('name', '?')} [{item.get('category', '?')}]: "
            f"{_money(item.get('estimated_cost_usd'))}, {item.get('duration_hours', '?')} h"
            + _link(item)
        )
    return lines


def _budget_lines(result) -> list:
    if not isinstance(result, dict) or "error" in result:
        return [f"  Error: {result.get('error') if isinstance(result, dict) else result}"]
    status = "OVER BUDGET" if result.get("over_budget") else "within budget"
    return [
        f"  Flight {_money(result.get('flight_cost_usd'))} + hotel {_money(result.get('hotel_total_usd'))}"
        f" + activities {_money(result.get('activities_cost_usd'))}"
        f" = {_money(result.get('total_cost_usd'))}",
        f"  Budget {_money(result.get('budget_usd'))}, remaining {_money(result.get('remaining_usd'))}"
        f" ({status})",
    ]


_SECTIONS = {
    "search_flights": ("Flights", _flight_lines, lambda a: f"{a.get('origin')} -> {a.get('destination')}, "
                       f"{a.get('depart_date')}" + (f" to {a['return_date']}" if a.get("return_date") else "")),
    "search_hotels": ("Hotels", _hotel_lines, lambda a: f"{a.get('destination')}, "
                      f"{a.get('checkin')} to {a.get('checkout')}"),
    "search_activities": ("Activities", _activity_lines, lambda a: f"{a.get('destination')}"
                          + (f", interests: {a['interests']}" if a.get("interests") else "")),
    "analyze_budget": ("Budget check", _budget_lines, lambda a: ""),
}


def format_report(results: list) -> str:
    """Format (tool name, arguments, result) tuples from one plan."""
    if not results:
        return ""
    blocks = ["=" * 60, "DATA USED FOR THIS PLAN (straight from the specialist agents)", "=" * 60]
    for name, args, result in results:
        title, lines_for, describe = _SECTIONS.get(name, (name, lambda r: [f"  {r}"], lambda a: ""))
        query = describe(args)
        blocks.append(f"\n{title}" + (f" — {query}" if query else ""))
        blocks.extend(lines_for(result) or ["  (no options returned)"])
    return "\n".join(blocks)
