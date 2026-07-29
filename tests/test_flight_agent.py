from unittest.mock import patch

from src.agents.flight_agent import _search_flights_impl


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search")
def test_search_flights_parses_agent_response(mock_call, _mock_client):
    mock_call.return_value = (
        '[{"airline": "Test Air", "price_usd": 450, "departure_time": "08:00", '
        '"arrival_time": "11:00", "stops": 0, "duration": "3h", "notes": "nonstop"}]'
    )

    result = _search_flights_impl("NYC", "LAX", "2026-09-01", "2026-09-08")

    assert isinstance(result, list)
    assert result[0]["airline"] == "Test Air"
    assert result[0]["price_usd"] == 450

    args, kwargs = mock_call.call_args
    assert "NYC" in args[2] or "NYC" in str(kwargs)


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search")
def test_search_flights_one_way_message(mock_call, _mock_client):
    mock_call.return_value = "[]"
    _search_flights_impl("NYC", "LAX", "2026-09-01")
    call_args = mock_call.call_args[0]
    user_message = call_args[2]
    assert "one-way" in user_message
