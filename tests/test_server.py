import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server import app as server_app
from server import auth
from server.store import MemoryStore

USER = {"id": "11111111-1111-1111-1111-111111111111", "email": "maya@example.com",
        "email_confirmed": True, "is_admin": False}
ADMIN = {**USER, "id": "22222222-2222-2222-2222-222222222222", "email": "admin@example.com", "is_admin": True}
AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    server_app.store = MemoryStore()
    server_app.planner_client = object()
    with patch.object(auth, "_lookup_user", return_value=dict(USER)):
        yield TestClient(server_app.app)


def _fake_run_turn(client, messages, on_event):
    """Mimics one full plan: a budget tool call, then a reply."""
    messages.append({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "analyze_budget", "arguments": "{}"}}]})
    on_event({"type": "tool_started", "tool": "analyze_budget", "call_id": "c1"})
    result = {"flight_cost_usd": 505, "hotel_total_usd": 76, "activities_cost_usd": 142,
              "total_cost_usd": 723, "budget_usd": 1500, "remaining_usd": 777, "over_budget": False}
    messages.append({"role": "tool", "tool_call_id": "c1", "content": json.dumps(result)})
    on_event({"type": "tool_finished", "tool": "analyze_budget", "call_id": "c1", "result": result})
    on_event({"type": "fact_checking"})
    messages.append({"role": "assistant", "content": "Total $723, $777 left."})
    return "Total $723, $777 left."


def _events(response) -> list:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_requires_login():
    with patch.object(auth, "_lookup_user", return_value=None):
        test_client = TestClient(server_app.app)
        assert test_client.get("/api/me").status_code == 401
        assert test_client.get("/api/me", headers=AUTH).status_code == 401


def test_unconfirmed_email_is_rejected():
    with patch.object(auth, "_lookup_user", return_value={**USER, "email_confirmed": False}):
        response = TestClient(server_app.app).get("/api/me", headers=AUTH)
    assert response.status_code == 403 and "confirm your email" in response.json()["detail"]


def test_chat_streams_progress_then_result_and_saves_plan(client):
    with patch.object(server_app, "run_turn", side_effect=_fake_run_turn):
        response = client.post("/api/chat", json={"message": "Plan Marrakesh"}, headers=AUTH)

    events = _events(response)
    assert [e["type"] for e in events] == ["progress", "progress", "progress", "result"]
    assert events[0] == {"type": "progress", "status": "started", "tool": "analyze_budget",
                         "call_id": "c1", "label": "Budget check"}
    assert events[1]["summary"] == "$723 of $1,500 — within budget"
    result = events[-1]
    assert result["reply"] == "Total $723, $777 left." and result["issues"] == []
    assert result["usage"]["plans_today"] == 1

    plan = server_app.store.plans[result["plan_id"]]
    assert plan["user_email"] == "maya@example.com" and plan["used_tools"] is True
    conversation = client.get(f"/api/conversations/{result['conversation_id']}", headers=AUTH).json()
    assert conversation["title"] == "Plan Marrakesh"
    assert conversation["turns"][0]["data"][0][0] == "analyze_budget"


def test_follow_up_continues_the_same_conversation(client):
    with patch.object(server_app, "run_turn", side_effect=_fake_run_turn):
        first = _events(client.post("/api/chat", json={"message": "Plan Marrakesh"}, headers=AUTH))[-1]
        second = _events(client.post("/api/chat", json={"message": "Cheaper hotel?",
                                                        "conversation_id": first["conversation_id"]},
                                     headers=AUTH))[-1]

    assert second["conversation_id"] == first["conversation_id"]
    stored = server_app.store.conversations[first["conversation_id"]]["messages"]
    assert [m["content"] for m in stored if m["role"] == "user"] == ["Plan Marrakesh", "Cheaper hotel?"]


def test_daily_plan_limit(client):
    with patch.object(server_app, "run_turn", side_effect=_fake_run_turn), \
            patch.object(server_app.config, "PLANS_PER_USER_PER_DAY", 1):
        client.post("/api/chat", json={"message": "Plan Marrakesh"}, headers=AUTH)
        response = client.post("/api/chat", json={"message": "Plan Rome"}, headers=AUTH)

    assert response.status_code == 429 and "trip plans for today" in response.json()["detail"]


def test_site_wide_limit(client):
    with patch.object(server_app, "run_turn", side_effect=_fake_run_turn), \
            patch.object(server_app.config, "PLANS_PER_DAY_TOTAL", 1):
        client.post("/api/chat", json={"message": "Plan Marrakesh"}, headers=AUTH)
        response = client.post("/api/chat", json={"message": "Plan Rome"}, headers=AUTH)

    assert response.status_code == 429 and "used up for everyone" in response.json()["detail"]


def test_planner_failure_streams_friendly_error(client):
    with patch.object(server_app, "run_turn", side_effect=RuntimeError("boom")):
        events = _events(client.post("/api/chat", json={"message": "Plan Rome"}, headers=AUTH))

    assert events == [{"type": "error", "message": "Something went wrong while planning. Please try again."}]
    assert server_app.store.plans == {}


def test_cannot_read_someone_elses_conversation(client):
    other = server_app.store.create_conversation("someone-else", "Secret trip", [])
    assert client.get(f"/api/conversations/{other}", headers=AUTH).status_code == 404
    response = client.post("/api/chat", json={"message": "hi", "conversation_id": other}, headers=AUTH)
    assert response.status_code == 404


def test_feedback_is_saved_and_unknown_flags_dropped(client):
    with patch.object(server_app, "run_turn", side_effect=_fake_run_turn):
        plan_id = _events(client.post("/api/chat", json={"message": "Plan Rome"}, headers=AUTH))[-1]["plan_id"]

    response = client.post(f"/api/plans/{plan_id}/feedback", headers=AUTH,
                           json={"rating": -1, "comment": " Hotel price was off ", "flags": ["prices_wrong", "hack"]})

    assert response.status_code == 200
    plan = server_app.store.plans[plan_id]
    assert (plan["rating"], plan["comment"], plan["flags"]) == (-1, "Hotel price was off", ["prices_wrong"])


def test_admin_page_is_admin_only(client):
    assert client.get("/api/admin/plans", headers=AUTH).status_code == 403
    with patch.object(auth, "_lookup_user", return_value=dict(ADMIN)):
        response = TestClient(server_app.app).get("/api/admin/plans", headers=AUTH)
    assert response.status_code == 200 and "plans" in response.json()


def test_message_length_is_limited(client):
    response = client.post("/api/chat", json={"message": "x" * 2001}, headers=AUTH)
    assert response.status_code == 422
