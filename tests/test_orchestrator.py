import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.orchestrator import TOOLS, run_turn, tool_results


def _response(content="", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments))
    )


def test_tools_wired_correctly():
    names = {tool["function"]["name"] for tool in TOOLS}
    assert names == {
        "search_flights", "search_hotels", "search_activities", "get_destination_info", "analyze_budget",
    }


def test_run_turn_without_tools_appends_assistant_message_and_returns_text():
    client = MagicMock()
    client.chat.completions.create.return_value = _response("Where are you flying from?")

    messages = [{"role": "user", "content": "Plan a trip"}]
    reply = run_turn(client, messages)

    assert reply == "Where are you flying from?"
    assert messages[-1] == {"role": "assistant", "content": "Where are you flying from?"}

    sent = client.chat.completions.create.call_args.kwargs
    assert sent["messages"][0]["role"] == "system"
    assert sent["tools"] == TOOLS


def test_run_turn_runs_tool_and_feeds_result_back():
    client = MagicMock()
    budget_call = _tool_call(
        "call_1", "analyze_budget",
        {"total_budget_usd": 1000, "flight_cost_usd": 400, "hotel_cost_per_night_usd": 100, "nights": 2},
    )
    client.chat.completions.create.side_effect = [
        _response(tool_calls=[budget_call]),
        _response("Here is your itinerary."),
    ]

    messages = [{"role": "user", "content": "Plan a trip"}]
    reply = run_turn(client, messages)

    assert reply == "Here is your itinerary."
    assert messages[1]["tool_calls"][0]["function"]["name"] == "analyze_budget"
    tool_message = messages[2]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"
    assert json.loads(tool_message["content"])["total_cost_usd"] == 600


def test_run_turn_reports_tool_errors_to_the_model():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _response(tool_calls=[_tool_call("call_1", "search_flights", {"origin": "ORD"})]),
        _response("Sorry, flight search failed."),
    ]

    with patch.dict("src.orchestrator._AGENTS", {"search_flights": MagicMock(side_effect=RuntimeError("boom"))}):
        messages = [{"role": "user", "content": "Plan a trip"}]
        run_turn(client, messages)

    assert "boom" in json.loads(messages[2]["content"])["error"]


def test_run_turn_stops_at_tool_round_limit():
    client = MagicMock()
    client.chat.completions.create.return_value = _response(
        tool_calls=[_tool_call("call_1", "unknown_tool", {})]
    )

    with patch("src.orchestrator.MAX_TOOL_ROUNDS", 2):
        reply = run_turn(client, [{"role": "user", "content": "Plan a trip"}])

    assert "limit" in reply
    assert client.chat.completions.create.call_count == 2


def test_run_turn_drops_null_optional_arguments():
    client = MagicMock()
    budget_call = _tool_call(
        "call_1", "analyze_budget",
        {"total_budget_usd": 1000, "flight_cost_usd": 400, "hotel_cost_per_night_usd": 100,
         "nights": 2, "activities_cost_usd": None},
    )
    client.chat.completions.create.side_effect = [
        _response(tool_calls=[budget_call]),
        _response("Done."),
    ]

    messages = [{"role": "user", "content": "Plan a trip"}]
    run_turn(client, messages)

    assert json.loads(messages[2]["content"])["activities_cost_usd"] == 0.0


HOTEL_RESULTS = [("search_hotels", {}, {"source": "Google Hotels via SerpApi (real prices)",
                                         "options": [{"name": "Hotel Atlas", "price_per_night_usd": 15,
                                                      "total_usd": 76}]})]


def test_fact_check_revision_is_kept_when_it_fixes_errors():
    from src.orchestrator import _fact_checked

    client = MagicMock()
    client.chat.completions.create.return_value = _response("Hotel Atlas: $76 total.")

    assert _fact_checked(client, "Hotel Atlas: $75 total.", HOTEL_RESULTS) == "Hotel Atlas: $76 total."


def test_fact_check_keeps_original_when_revision_fails_or_is_worse():
    from src.orchestrator import _fact_checked

    failing = MagicMock()
    failing.chat.completions.create.side_effect = RuntimeError("rate limited")
    assert _fact_checked(failing, "Hotel Atlas: $75 total.", HOTEL_RESULTS) == "Hotel Atlas: $75 total."

    worse = MagicMock()
    worse.chat.completions.create.return_value = _response("Hotel Atlas: $75 total, $74 really.")
    assert _fact_checked(worse, "Hotel Atlas: $75 total.", HOTEL_RESULTS) == "Hotel Atlas: $75 total."


def test_fact_check_skips_editor_when_reply_is_correct():
    from src.orchestrator import _fact_checked

    client = MagicMock()
    assert _fact_checked(client, "Hotel Atlas: $76 total.", HOTEL_RESULTS) == "Hotel Atlas: $76 total."
    client.chat.completions.create.assert_not_called()


def test_run_turn_reports_progress_events():
    client = MagicMock()
    budget_call = _tool_call(
        "call_1", "analyze_budget",
        {"total_budget_usd": 1000, "flight_cost_usd": 400, "hotel_cost_per_night_usd": 100, "nights": 2},
    )
    client.chat.completions.create.side_effect = [
        _response(tool_calls=[budget_call]),
        _response("Plan ready."),
    ]
    events = []

    run_turn(client, [{"role": "user", "content": "Plan a trip"}], on_event=events.append)

    assert [e["type"] for e in events] == ["tool_started", "tool_finished", "fact_checking"]
    assert events[0] == {"type": "tool_started", "tool": "analyze_budget", "call_id": "call_1"}
    assert events[1]["result"]["total_cost_usd"] == 600


def test_repeated_search_runs_once_and_is_not_reported_twice():
    client = MagicMock()
    flight_args = {"origin": "JFK", "destination": "LIS", "depart_date": "2027-05-20", "return_date": None}
    client.chat.completions.create.side_effect = [
        # Same search twice in one round, then again in the next round.
        _response(tool_calls=[_tool_call("c1", "search_flights", flight_args),
                              _tool_call("c2", "search_flights", flight_args)]),
        _response(tool_calls=[_tool_call("c3", "search_flights", {**flight_args, "return_date": None})]),
        _response("Done."),
    ]
    fake_search = MagicMock(return_value={"source": "Google Flights (real fares)", "options": []})
    events = []

    with patch.dict("src.orchestrator._AGENTS", {"search_flights": fake_search}):
        messages = [{"role": "user", "content": "Plan a trip"}]
        run_turn(client, messages, on_event=events.append)

    fake_search.assert_called_once()
    assert [e["call_id"] for e in events if e["type"] == "tool_started"] == ["c1"]
    tool_messages = [m for m in messages if m["role"] == "tool"]
    assert len(tool_messages) == 3  # every call still gets an answer
    assert json.loads(tool_messages[1]["content"])["_duplicate"] is True
    assert [name for name, _, _ in tool_results(messages)] == ["search_flights"]


def test_same_tool_with_different_inputs_still_runs():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _response(tool_calls=[_tool_call("c1", "search_flights", {"origin": "JFK", "destination": "LIS",
                                                                  "depart_date": "2027-05-20"}),
                              _tool_call("c2", "search_flights", {"origin": "EWR", "destination": "LIS",
                                                                  "depart_date": "2027-05-20"})]),
        _response("Done."),
    ]
    fake_search = MagicMock(return_value={"options": []})

    with patch.dict("src.orchestrator._AGENTS", {"search_flights": fake_search}):
        run_turn(client, [{"role": "user", "content": "Plan a trip"}])

    assert fake_search.call_count == 2
