"""Budget-analysis specialist agent.

Unlike the search agents, this one is pure arithmetic — no LLM call needed.
Kept as its own "agent" tool so the orchestrator has a dedicated, reliable
way to check estimates against the traveler's stated budget.
"""

TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_budget",
        "description": "Check estimated trip costs against the traveler's total budget.",
        "parameters": {
            "type": "object",
            "properties": {
                "total_budget_usd": {
                    "type": "number",
                    "description": "The traveler's total budget for the trip, in USD.",
                },
                "flight_cost_usd": {
                    "type": "number",
                    "description": "Estimated round-trip (or one-way) flight cost, in USD.",
                },
                "hotel_cost_per_night_usd": {
                    "type": "number",
                    "description": "Estimated hotel cost per night, in USD.",
                },
                "nights": {"type": "integer", "description": "Number of nights of lodging."},
                "activities_cost_usd": {
                    "type": ["number", "null"],
                    "description": "Estimated total cost of planned activities, in USD.",
                },
            },
            "required": ["total_budget_usd", "flight_cost_usd", "hotel_cost_per_night_usd", "nights"],
        },
    },
}


def analyze_budget(
    total_budget_usd: float,
    flight_cost_usd: float,
    hotel_cost_per_night_usd: float,
    nights: int,
    activities_cost_usd: float = 0.0,
) -> dict:
    hotel_total_usd = round(hotel_cost_per_night_usd * nights, 2)
    total_cost_usd = round(flight_cost_usd + hotel_total_usd + activities_cost_usd, 2)
    remaining_usd = round(total_budget_usd - total_cost_usd, 2)

    return {
        "flight_cost_usd": round(flight_cost_usd, 2),
        "hotel_total_usd": hotel_total_usd,
        "activities_cost_usd": round(activities_cost_usd, 2),
        "total_cost_usd": total_cost_usd,
        "budget_usd": round(total_budget_usd, 2),
        "remaining_usd": remaining_usd,
        "over_budget": remaining_usd < 0,
    }
