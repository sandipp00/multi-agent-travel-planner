from src.agents.budget_agent import _analyze_budget_impl


def test_under_budget():
    result = _analyze_budget_impl(
        total_budget_usd=3000,
        flight_cost_usd=800,
        hotel_cost_per_night_usd=150,
        nights=5,
        activities_cost_usd=200,
    )
    assert result["hotel_total_usd"] == 750
    assert result["total_cost_usd"] == 1750
    assert result["remaining_usd"] == 1250
    assert result["over_budget"] is False


def test_over_budget():
    result = _analyze_budget_impl(
        total_budget_usd=1000,
        flight_cost_usd=800,
        hotel_cost_per_night_usd=150,
        nights=5,
        activities_cost_usd=200,
    )
    assert result["total_cost_usd"] == 1750
    assert result["remaining_usd"] == -750
    assert result["over_budget"] is True


def test_defaults_activities_to_zero():
    result = _analyze_budget_impl(
        total_budget_usd=1000,
        flight_cost_usd=400,
        hotel_cost_per_night_usd=100,
        nights=2,
    )
    assert result["activities_cost_usd"] == 0.0
    assert result["total_cost_usd"] == 600
