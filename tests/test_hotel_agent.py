from unittest.mock import patch

from src.agents.hotel_agent import _search_hotels_impl


@patch("src.agents.hotel_agent.get_client", return_value="fake-client")
@patch("src.agents.hotel_agent.call_with_web_search")
def test_search_hotels_parses_agent_response(mock_call, _mock_client):
    mock_call.return_value = (
        '[{"name": "Test Hotel", "area": "Downtown", "price_per_night_usd": 120, '
        '"rating": 4.3, "notes": "central"}]'
    )

    result = _search_hotels_impl("Chicago", "2026-09-01", "2026-09-05")

    assert result[0]["name"] == "Test Hotel"
    assert result[0]["price_per_night_usd"] == 120


@patch("src.agents.hotel_agent.get_client", return_value="fake-client")
@patch("src.agents.hotel_agent.call_with_web_search")
def test_search_hotels_includes_budget_hint(mock_call, _mock_client):
    mock_call.return_value = "[]"
    _search_hotels_impl("Chicago", "2026-09-01", "2026-09-05", budget_per_night_usd="150")
    user_message = mock_call.call_args[0][2]
    assert "150" in user_message
