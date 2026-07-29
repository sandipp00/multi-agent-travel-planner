from unittest.mock import MagicMock

from src.orchestrator import TOOLS, build_runner, run_turn


def test_tools_wired_correctly():
    names = {tool.name for tool in TOOLS}
    assert names == {"search_flights", "search_hotels", "search_activities", "analyze_budget"}


def test_build_runner_calls_tool_runner_with_expected_args():
    fake_client = MagicMock()
    messages = [{"role": "user", "content": "Plan a trip"}]

    build_runner(fake_client, messages)

    fake_client.beta.messages.tool_runner.assert_called_once()
    _, kwargs = fake_client.beta.messages.tool_runner.call_args
    assert kwargs["tools"] == TOOLS
    assert kwargs["messages"] == messages
    assert kwargs["system"]


def test_run_turn_appends_assistant_message_and_returns_text():
    fake_client = MagicMock()
    text_block = MagicMock(type="text", text="Here is your itinerary.")
    final_message = MagicMock(content=[text_block], stop_reason="end_turn")
    fake_client.beta.messages.tool_runner.return_value = [final_message]

    messages = [{"role": "user", "content": "Plan a trip"}]
    reply = run_turn(fake_client, messages)

    assert reply == "Here is your itinerary."
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == final_message.content


def test_run_turn_handles_refusal():
    fake_client = MagicMock()
    final_message = MagicMock(content=[], stop_reason="refusal")
    fake_client.beta.messages.tool_runner.return_value = [final_message]

    messages = [{"role": "user", "content": "Plan a trip"}]
    reply = run_turn(fake_client, messages)

    assert "declined" in reply.lower()
