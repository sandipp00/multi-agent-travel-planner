from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.llm_client import call_with_web_search, web_search


def _client(reply):
    client = MagicMock()
    message = SimpleNamespace(content=reply)
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )
    return client


def _prompt(client):
    return client.chat.completions.create.call_args.kwargs["messages"][1]["content"]


@patch("src.llm_client.web_search")
def test_puts_search_results_in_prompt(mock_search):
    mock_search.return_value = [
        {"title": "Cheap flights", "href": "https://example.com", "body": "From $216"}
    ]
    client = _client('[{"a": 1}]')

    reply = call_with_web_search(
        client, "system", "find flights", "test-model", search_query="flights ORD LIS"
    )

    assert reply == '[{"a": 1}]'
    mock_search.assert_called_once_with("flights ORD LIS")
    assert "Cheap flights" in _prompt(client)
    assert "From $216" in _prompt(client)
    system = client.chat.completions.create.call_args.kwargs["messages"][0]
    assert system == {"role": "system", "content": "system"}


@patch("src.llm_client.web_search", return_value=[])
def test_falls_back_to_estimates_without_results(_mock_search):
    client = _client("[]")

    call_with_web_search(client, "system", "find flights", "test-model")

    assert "No web results" in _prompt(client)


@patch("src.llm_client.web_search", return_value=[])
def test_uses_user_message_when_no_search_query(mock_search):
    call_with_web_search(_client("[]"), "system", "find flights", "test-model")

    mock_search.assert_called_once_with("find flights")


@patch("src.llm_client.DDGS")
def test_web_search_returns_empty_on_failure(mock_ddgs):
    mock_ddgs.return_value.text.side_effect = RuntimeError("rate limited")

    assert web_search("anything") == []
