from types import SimpleNamespace
from unittest.mock import MagicMock

from src.fact_check import check, revise

# Trimmed from the real LHR -> RAK run.
RESULTS = [
    ("search_flights", {}, {"source": "Google Flights (real fares)", "options": [
        {"airline": "SWISS, Edelweiss Air", "price_usd": 366,
         "notes": "Real fare from Google Flights (round-trip total). Layover 12h 0m in ZRH (long — likely overnight)."},
        {"airline": "Air France", "price_usd": 457,
         "notes": "Real fare from Google Flights (round-trip total). Layover 12h 0m in CDG (long — likely overnight)."},
        {"airline": "Royal Air Maroc", "price_usd": 505,
         "notes": "Real fare from Google Flights (round-trip total). Layover 1h 5m in CMN."},
        {"airline": "Air France", "price_usd": 528,
         "notes": "Real fare from Google Flights (round-trip total). Layover 1h 0m in CDG."},
    ]}),
    ("search_hotels", {}, {"source": "Google Hotels via SerpApi (real prices)", "options": [
        {"name": "Hôtel Atlas", "price_per_night_usd": 15, "total_usd": 76},
    ]}),
    ("search_activities", {}, [{"name": "Jardin Majorelle", "estimated_cost_usd": 10}]),
    ("analyze_budget", {}, {"flight_cost_usd": 505, "hotel_total_usd": 76, "activities_cost_usd": 142,
                            "total_cost_usd": 723, "budget_usd": 1500, "remaining_usd": 777,
                            "over_budget": False}),
]


def test_catches_price_paired_with_wrong_airline():
    reply = ("**Price:** **$505** – saving ≈ 12 hours compared with the cheapest $366 "
             "Air‑France itinerary that includes a 12-hour overnight layover.")

    issues = check(reply, RESULTS)

    assert any("$366 belongs to SWISS, Edelweiss Air ($366), not Air France" in i for i in issues)


def test_catches_miscopied_layover_length():
    issues = check("The cheapest SWISS itinerary includes a 13‑hour overnight layover.", RESULTS)

    assert any("no layover of about 13 hours" in i and "12h 0m" in i for i in issues)


def test_catches_rounded_hotel_total():
    issues = check("**Rate:** **$15 / night** → **$75 total** for 5 nights at Hôtel Atlas.", RESULTS)

    assert issues == ['"**Rate:** **$15 / night** → **$75 total** for 5 nights at Hôtel Atlas." — '
                      "$75 should be $76 (the exact figure in the data)."]


def test_correct_reply_passes():
    reply = "\n".join([
        "**Airline:** Royal Air Maroc, $505 round trip, 1h 5m layover in Casablanca.",
        "It costs $139 more than SWISS ($366) but avoids a 12-hour overnight layover.",
        "| Hotel – Hotel Atlas | $76 for 5 nights ($15/night) |",
        "| **Total** | **$723** | **Remaining** | **$1 500** budget, **$777** left |",
        "Dinner at a rooftop cafe, about $20.",
    ])

    assert check(reply, RESULTS) == []


def test_revise_sends_issues_and_plan_to_the_editor():
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="fixed plan"))]
    )

    assert revise(client, "original plan", ["$75 should be $76"]) == "fixed plan"
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "$75 should be $76" in prompt and "original plan" in prompt
