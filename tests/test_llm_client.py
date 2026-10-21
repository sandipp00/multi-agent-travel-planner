from types import SimpleNamespace
from unittest.mock import MagicMock

from src.llm_client import call_with_web_search


def _response(stop_reason, text=""):
    blocks = [SimpleNamespace(type="text", text=text)] if text else []
    return SimpleNamespace(stop_reason=stop_reason, content=blocks)


def _call(client, **kwargs):
    return call_with_web_search(client, "system", "find flights", "test-model", **kwargs)


def test_returns_text_on_end_turn():
    client = MagicMock()
    client.messages.create.return_value = _response("end_turn", '[{"a": 1}]')

    assert _call(client) == '[{"a": 1}]'
    assert client.messages.create.call_count == 1


def test_resends_after_pause_turn():
    client = MagicMock()
    paused = _response("pause_turn")
    client.messages.create.side_effect = [paused, _response("end_turn", "done")]

    assert _call(client) == "done"
    assert client.messages.create.call_count == 2

    resent = client.messages.create.call_args.kwargs["messages"]
    assert resent[-1] == {"role": "assistant", "content": paused.content}


def test_stops_after_continuation_limit():
    client = MagicMock()
    client.messages.create.return_value = _response("pause_turn")

    result = _call(client, max_continuations=2)

    assert "continuation limit" in result
    assert client.messages.create.call_count == 3


def test_refusal_returns_error_json():
    client = MagicMock()
    client.messages.create.return_value = _response("refusal")

    assert "declined" in _call(client)
