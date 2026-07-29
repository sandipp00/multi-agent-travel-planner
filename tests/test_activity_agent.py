from unittest.mock import patch

from src.agents.activity_agent import _search_activities_impl


@patch("src.agents.activity_agent.get_client", return_value="fake-client")
@patch("src.agents.activity_agent.call_with_web_search")
def test_search_activities_parses_agent_response(mock_call, _mock_client):
    mock_call.return_value = (
        '[{"name": "City Museum", "category": "museum", "estimated_cost_usd": 20, '
        '"duration_hours": 2, "notes": "popular"}]'
    )

    result = _search_activities_impl("Chicago", "2026-09-01", "2026-09-05", interests="museums")

    assert result[0]["name"] == "City Museum"


@patch("src.agents.activity_agent.get_client", return_value="fake-client")
@patch("src.agents.activity_agent.call_with_web_search")
def test_search_activities_includes_interests(mock_call, _mock_client):
    mock_call.return_value = "[]"
    _search_activities_impl("Chicago", "2026-09-01", "2026-09-05", interests="hiking, food")
    user_message = mock_call.call_args[0][2]
    assert "hiking, food" in user_message
