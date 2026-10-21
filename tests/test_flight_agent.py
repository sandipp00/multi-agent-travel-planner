import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

from src.agents.flight_agent import BOOKING_HORIZON_DAYS, search_flights


def _leg(from_code, to_code, depart, arrive, minutes):
    return SimpleNamespace(
        from_airport=SimpleNamespace(code=from_code),
        to_airport=SimpleNamespace(code=to_code),
        departure=SimpleNamespace(date=depart[0], time=depart[1]),
        arrival=SimpleNamespace(date=arrive[0], time=arrive[1]),
        duration=minutes,
    )


def _fare(price, airlines, legs):
    return SimpleNamespace(price=price, airlines=airlines, flights=legs)


@patch("src.agents.flight_agent.call_with_web_search")
@patch("src.agents.flight_agent.get_flights")
def test_uses_real_google_flights_fares(mock_get_flights, mock_call):
    mock_get_flights.return_value = [
        _fare(1099, ["SWISS"], [
            _leg("ORD", "ZRH", ((2027, 9, 7), (14, 20)), ((2027, 9, 8), (6, 10)), 530),
            _leg("ZRH", "LIS", ((2027, 9, 8), (9, 10)), ((2027, 9, 8), (11, 5)), 175),
        ]),
        _fare(920, ["Turkish Airlines"], [
            _leg("ORD", "IST", ((2027, 9, 7), (20, 5)), ((2027, 9, 8), (14, 50)), 645),
            _leg("IST", "LIS", ((2027, 9, 9), (6, 55)), ((2027, 9, 9), (9, 55)), 300),
        ]),
    ]

    result = search_flights("ord", "LIS", "2027-09-07", "2027-09-12")

    mock_call.assert_not_called()
    assert result["source"] == "Google Flights (real fares)"
    assert "warning" not in result
    cheapest = result["options"][0]
    assert cheapest["airline"] == "Turkish Airlines"
    assert cheapest["price_usd"] == 920
    assert cheapest["departure_time"] == "2027-09-07 20:05"
    assert cheapest["arrival_time"] == "2027-09-09 09:55"
    assert cheapest["stops"] == 1
    assert cheapest["duration"] == "15h 45m flying time"
    assert "round-trip" in cheapest["notes"] and "IST" in cheapest["notes"]
    assert result["options"][1]["price_usd"] == 1099


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search")
@patch("src.agents.flight_agent.get_flights", side_effect=RuntimeError("Google changed"))
def test_falls_back_to_web_search_when_google_flights_fails(_mock_get_flights, mock_call, _mock_client):
    mock_call.return_value = (
        '[{"airline": "Test Air", "price_usd": 450, "departure_time": "08:00", '
        '"arrival_time": "11:00", "stops": 0, "duration": "3h", "notes": "nonstop"}]'
    )

    result = search_flights("JFK", "LAX", "2026-09-01", "2026-09-08")

    assert result["options"][0]["airline"] == "Test Air"
    assert result["warning"].startswith("ESTIMATES ONLY")
    assert "JFK" in mock_call.call_args[0][2]


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search", return_value="[]")
@patch("src.agents.flight_agent.get_flights")
def test_city_names_skip_google_flights(mock_get_flights, mock_call, _mock_client):
    result = search_flights("New York", "Los Angeles", "2026-09-01")

    mock_get_flights.assert_not_called()
    assert "one-way" in mock_call.call_args[0][2]
    assert "IATA" in result["warning"]


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search", return_value="[]")
@patch("src.agents.flight_agent.get_flights", return_value=[])
def test_falls_back_when_google_flights_has_no_results(_mock_get_flights, mock_call, _mock_client):
    search_flights("JFK", "LAX", "2026-09-01")

    mock_call.assert_called_once()


@patch("src.agents.flight_agent.get_client", return_value="fake-client")
@patch("src.agents.flight_agent.call_with_web_search", return_value="[]")
@patch("src.agents.flight_agent.get_flights", return_value=[])
def test_warns_when_dates_are_past_booking_horizon(_mock_get_flights, _mock_call, _mock_client):
    far = (dt.date.today() + dt.timedelta(days=BOOKING_HORIZON_DAYS + 20)).isoformat()

    result = search_flights("JFK", "FCO", far)

    assert "haven't published fares" in result["warning"]
