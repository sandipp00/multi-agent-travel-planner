from unittest.mock import MagicMock, patch

from src.agents.hotel_agent import search_hotels

SERPAPI_RESPONSE = {
    "properties": [
        {"name": "Hotel Artemide", "hotel_class": "4-star hotel", "overall_rating": 4.6, "reviews": 3120,
         "rate_per_night": {"lowest": "$214", "extracted_lowest": 214},
         "total_rate": {"lowest": "$856", "extracted_lowest": 856},
         "link": "https://www.hotelartemide.it/"},
        {"name": "Radio Hotel", "type": "hotel", "overall_rating": 4.1,
         "rate_per_night": {"extracted_lowest": 98}},
        # No price — must be skipped.
        {"name": "Unpriced Inn", "overall_rating": 4.0},
    ]
}


def _http_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    return response


@patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"})
@patch("src.agents.hotel_agent.call_with_web_search")
@patch("src.agents.hotel_agent.httpx.get", return_value=_http_response(SERPAPI_RESPONSE))
def test_uses_real_google_hotels_prices(mock_get, mock_call):
    result = search_hotels("Rome", "2027-09-06", "2027-09-10", budget_per_night_usd="200")

    mock_call.assert_not_called()
    params = mock_get.call_args.kwargs["params"]
    assert params["engine"] == "google_hotels" and params["q"] == "hotels in Rome"
    assert params["check_in_date"] == "2027-09-06" and params["check_out_date"] == "2027-09-10"
    assert params["max_price"] == 250

    assert result["source"] == "Google Hotels via SerpApi (real prices)"
    assert "warning" not in result
    names = [opt["name"] for opt in result["options"]]
    assert names == ["Radio Hotel", "Hotel Artemide"]  # cheapest first, unpriced skipped
    artemide = result["options"][1]
    assert artemide["price_per_night_usd"] == 214 and artemide["total_usd"] == 856
    assert artemide["area"] == "4-star hotel" and artemide["source_url"] == "https://www.hotelartemide.it/"


@patch.dict("os.environ", {"SERPAPI_API_KEY": ""})
@patch("src.agents.hotel_agent.get_client", return_value="fake-client")
@patch("src.agents.hotel_agent.call_with_web_search")
@patch("src.agents.hotel_agent.httpx.get")
def test_without_key_falls_back_to_flagged_estimates(mock_get, mock_call, _mock_client):
    mock_call.return_value = (
        '[{"name": "Test Hotel", "area": "Downtown", "price_per_night_usd": 120, '
        '"rating": 4.3, "notes": "central"}]'
    )

    result = search_hotels("Chicago", "2026-09-01", "2026-09-05", budget_per_night_usd="150")

    mock_get.assert_not_called()
    assert result["options"][0]["name"] == "Test Hotel"
    assert "no SERPAPI_API_KEY" in result["warning"]
    assert "150" in mock_call.call_args[0][2]


@patch.dict("os.environ", {"SERPAPI_API_KEY": "secret-key-123"})
@patch("src.agents.hotel_agent.get_client", return_value="fake-client")
@patch("src.agents.hotel_agent.call_with_web_search", return_value="[]")
@patch("src.agents.hotel_agent.httpx.get", side_effect=RuntimeError("GET https://serpapi.com/search?api_key=secret-key-123"))
def test_serpapi_failure_falls_back_without_leaking_key(_mock_get, _mock_call, _mock_client):
    result = search_hotels("Rome", "2027-09-06", "2027-09-10")

    assert "SerpApi request failed (RuntimeError)" in result["warning"]
    assert "secret-key-123" not in str(result)


@patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"})
@patch("src.agents.hotel_agent.get_client", return_value="fake-client")
@patch("src.agents.hotel_agent.call_with_web_search", return_value="[]")
@patch("src.agents.hotel_agent.httpx.get", return_value=_http_response({"error": "Your account has run out of searches."}))
def test_serpapi_error_message_is_reported(_mock_get, _mock_call, _mock_client):
    result = search_hotels("Rome", "2027-09-06", "2027-09-10")

    assert "run out of searches" in result["warning"]
