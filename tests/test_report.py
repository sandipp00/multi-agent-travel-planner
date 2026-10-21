import json

from src.orchestrator import tool_results
from src.report import format_report


def _call(call_id, name, args):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_tool_results_pairs_calls_with_results_from_this_turn():
    messages = [
        {"role": "user", "content": "earlier turn"},
        {"role": "assistant", "content": "", "tool_calls": [_call("old", "analyze_budget", {})]},
        {"role": "tool", "tool_call_id": "old", "content": "{}"},
        {"role": "user", "content": "plan it"},
        {"role": "assistant", "content": "", "tool_calls": [
            _call("c1", "search_hotels", {"destination": "Rome"}),
            _call("c2", "analyze_budget", {"nights": 4}),
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": '[{"name": "Radio Hotel"}]'},
        {"role": "tool", "tool_call_id": "c2", "content": '{"total_cost_usd": 900}'},
        {"role": "assistant", "content": "Here is your plan."},
    ]

    results = tool_results(messages, start=3)

    assert results == [
        ("search_hotels", {"destination": "Rome"}, [{"name": "Radio Hotel"}]),
        ("analyze_budget", {"nights": 4}, {"total_cost_usd": 900}),
    ]


def test_report_shows_every_section_with_prices_and_links():
    report = format_report([
        ("search_flights", {"origin": "JFK", "destination": "FCO", "depart_date": "2027-09-06",
                            "return_date": "2027-09-10"},
         {"source": "Google Flights (real fares)", "source_url": "https://www.google.com/travel/flights/x",
          "options": [{"airline": "Air Serbia", "price_usd": 774, "departure_time": "2027-09-06 13:50",
                       "arrival_time": "2027-09-07 08:25", "stops": 1, "duration": "12h flying time",
                       "notes": "Real fare"}]}),
        ("search_hotels", {"destination": "Rome", "checkin": "2027-09-06", "checkout": "2027-09-10"},
         [{"name": "Radio Hotel", "area": "Trastevere", "price_per_night_usd": 68, "rating": 4.1,
           "source_url": "https://example.com/radio"}]),
        ("search_activities", {"destination": "Rome", "interests": "art"},
         [{"name": "Vatican Museums", "category": "art", "estimated_cost_usd": 30, "duration_hours": 3,
           "source_url": ""}]),
        ("analyze_budget", {}, {"flight_cost_usd": 774, "hotel_total_usd": 272, "activities_cost_usd": 30,
                                "total_cost_usd": 1076, "budget_usd": 2000, "remaining_usd": 924,
                                "over_budget": False}),
    ])

    assert "Flights — JFK -> FCO, 2027-09-06 to 2027-09-10" in report
    assert "Air Serbia: $774" in report and "https://www.google.com/travel/flights/x" in report
    assert "Radio Hotel (Trastevere): $68/night" in report and "https://example.com/radio" in report
    assert "Vatican Museums [art]: $30" in report and "no source link — estimate" in report
    assert "= $1,076" in report and "remaining $924 (within budget)" in report


def test_report_shows_warnings_and_errors():
    report = format_report([
        ("search_flights", {"origin": "JFK", "destination": "FCO", "depart_date": "2027-10-04"},
         {"source": "web search estimates", "warning": "ESTIMATES ONLY — too far ahead.", "options": []}),
        ("search_hotels", {"destination": "Rome"}, {"error": "search_hotels failed: boom"}),
        ("search_activities", {"destination": "Rome"}, {"raw": "not json"}),
    ])

    assert "Warning: ESTIMATES ONLY" in report
    assert "Error: search_hotels failed: boom" in report
    assert "not valid JSON" in report


def test_empty_report_when_no_tools_ran():
    assert format_report([]) == ""
