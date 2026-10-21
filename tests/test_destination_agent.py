import datetime as dt
from unittest.mock import patch

from src.agents.destination_agent import _weather_window, get_destination_info

NOMINATIM = [{"display_name": "Roma, Lazio, Italia", "lat": "41.89", "lon": "12.48",
              "address": {"country_code": "it"}}]
WEATHER = {"daily": {"temperature_2m_max": [30.0, 28.0], "temperature_2m_min": [19.0, 17.0],
                     "precipitation_sum": [0.0, 4.2]}}
RATES = {"rates": {"EUR": 0.89}, "time_last_update_utc": "Wed, 21 Oct 2026 00:02:32 +0000"}
WIKIDATA = {"results": {"bindings": [
    {"item": {"value": "Q10285"}, "itemLabel": {"value": "Colosseum"},
     "typeLabel": {"value": "archaeological site"}, "website": {"value": "https://colosseo.it"}},
    # Same place again with a second type — must be deduplicated.
    {"item": {"value": "Q10285"}, "itemLabel": {"value": "Colosseum"},
     "typeLabel": {"value": "tourist attraction"}},
    {"item": {"value": "Q180402"}, "itemLabel": {"value": "Roman Forum"},
     "typeLabel": {"value": "archaeological site"}},
]}}
WIKIVOYAGE = {"query": {"pages": {"1": {"title": "Rome", "extract": "Rome, the Eternal City."}}}}


def _fake_get_json(url, params=None):
    if "nominatim" in url:
        return NOMINATIM
    if "open-meteo" in url:
        return WEATHER
    if "er-api" in url:
        return RATES
    if "wikidata" in url:
        return WIKIDATA
    if "wikivoyage" in url:
        return WIKIVOYAGE
    raise AssertionError(f"unexpected URL {url}")


@patch("src.agents.destination_agent._get_json", side_effect=_fake_get_json)
def test_combines_all_parts(_mock):
    result = get_destination_info("Rome, Italy", "2027-09-06", "2027-09-10")

    assert result["location"] == "Roma, Lazio, Italia"
    weather = result["weather"]
    assert weather["avg_high_c"] == 29.0 and weather["avg_low_c"] == 18.0
    assert weather["avg_high_f"] == 84 and weather["rainy_days"] == 1
    assert "typical-weather guide" in weather["basis"]
    assert result["currency"]["local_currency"] == "EUR"
    assert result["currency"]["example"] == "100 USD = 89.0 EUR"
    assert [s["name"] for s in result["sights"]] == ["Colosseum", "Roman Forum"]
    assert result["sights"][0]["website"] == "https://colosseo.it"
    assert result["guide"]["url"] == "https://en.wikivoyage.org/wiki/Rome"


@patch("src.agents.destination_agent._get_json")
def test_one_failing_service_does_not_break_the_rest(mock_get_json):
    def flaky(url, params=None):
        if "wikidata" in url:
            raise TimeoutError("timed out")
        return _fake_get_json(url, params)
    mock_get_json.side_effect = flaky

    result = get_destination_info("Rome, Italy", "2027-09-06", "2027-09-10")

    assert "sights unavailable" in result["sights"]["error"]
    assert result["currency"]["local_currency"] == "EUR"


@patch("src.agents.destination_agent._get_json", side_effect=_fake_get_json)
def test_same_currency_skips_exchange_rate(mock_get_json):
    result = get_destination_info("Rome, Italy", "2027-09-06", "2027-09-10", home_currency="eur")

    assert result["currency"] == {"local_currency": "EUR", "home_currency": "EUR", "rate": 1.0}
    assert not any("er-api" in call.args[0] for call in mock_get_json.call_args_list)


@patch("src.agents.destination_agent._get_json", return_value=[])
def test_unknown_place_returns_error(_mock):
    result = get_destination_info("Nowhereville", "2027-09-06", "2027-09-10")

    assert "location lookup failed" in result["error"]


def test_weather_window_uses_forecast_for_near_trips():
    today = dt.date(2026, 10, 22)
    kind, start, end = _weather_window(dt.date(2026, 10, 25), dt.date(2026, 10, 28), today)
    assert (kind, start, end) == ("forecast", dt.date(2026, 10, 25), dt.date(2026, 10, 28))


def test_weather_window_uses_most_recent_past_year_for_far_trips():
    today = dt.date(2026, 10, 22)
    assert _weather_window(dt.date(2027, 9, 6), dt.date(2027, 9, 10), today) == (
        "typical", dt.date(2026, 9, 6), dt.date(2026, 9, 10))
    # Last year's dates haven't fully happened yet, so go back one more year.
    assert _weather_window(dt.date(2027, 10, 20), dt.date(2027, 10, 25), today) == (
        "typical", dt.date(2025, 10, 20), dt.date(2025, 10, 25))
    # Feb 29 maps to Feb 28 in a non-leap year.
    assert _weather_window(dt.date(2028, 2, 29), dt.date(2028, 3, 2), today)[1] == dt.date(2026, 2, 28)
