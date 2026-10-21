import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.orchestrator import TOOLS, run_turn


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
