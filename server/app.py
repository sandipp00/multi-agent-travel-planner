"""Website backend: login-protected API around the travel planner.

Run locally:  uvicorn server.app:app --reload --port 8000
(the React dev server on :5173 proxies /api here).

A plan streams back as newline-delimited JSON on the same request, so it
works on serverless hosts that only give CPU while a request is open:
    {"type": "progress", "tool": ..., "status": "started" | "finished", ...}
    {"type": "result", "plan_id": ..., "conversation_id": ..., "reply": ..., ...}
    {"type": "error", "message": ...}
"""

import datetime as dt
import json
import queue
import threading
import time
from pathlib import Path

import groq
import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import config
from server.auth import admin_user, current_user
from server.progress import AGENT_LABELS, summarize
from server.store import SupabaseStore
from src.fact_check import check
from src.llm_client import get_client
from src.orchestrator import run_turn, tool_results

app = FastAPI(title="Travel Planner API")

# Swapped for MemoryStore in tests.
store = SupabaseStore()
planner_client = None  # created on first use, so the app starts without a Groq key


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_MESSAGE_CHARS)
    conversation_id: str | None = None


class FeedbackRequest(BaseModel):
    rating: int | None = Field(default=None, ge=-1, le=1)
    comment: str = Field(default="", max_length=2000)
    flags: list[str] = Field(default_factory=list, max_length=10)


def _start_of_today() -> str:
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today.isoformat()


def _usage(user: dict) -> dict:
    since = _start_of_today()
    return {
        "plans_today": store.count_plans_since(since, user["id"]),
        "plans_limit": config.PLANS_PER_USER_PER_DAY,
        "messages_today": store.count_messages_since(since, user["id"]),
        "messages_limit": config.MESSAGES_PER_USER_PER_DAY,
        "site_plans_today": store.count_plans_since(since),
        "site_plans_limit": config.PLANS_PER_DAY_TOTAL,
    }


def _limit_message(usage: dict) -> str | None:
    if usage["site_plans_today"] >= usage["site_plans_limit"]:
        return ("Today's free planning capacity is used up for everyone — the planner runs on free AI "
                "limits. Please try again tomorrow.")
    if usage["plans_today"] >= usage["plans_limit"]:
        return f"You've used your {usage['plans_limit']} trip plans for today. Please come back tomorrow."
    if usage["messages_today"] >= usage["messages_limit"]:
        return f"You've sent {usage['messages_limit']} messages today. Please come back tomorrow."
    return None


@app.get("/api/health")
def health():
    return {"ok": True, "missing_settings": config.missing_settings()}


_providers_cache: dict = {}
_PROVIDERS_CACHE_SECONDS = 300


def _google_enabled() -> bool:
    """Whether Google sign-in is switched on in the Supabase project."""
    cached = _providers_cache.get("google")
    if cached and cached[0] > time.time():
        return cached[1]
    try:
        response = httpx.get(f"{config.SUPABASE_URL}/auth/v1/settings",
                             headers={"apikey": config.SUPABASE_PUBLISHABLE_KEY}, timeout=10)
        enabled = bool(response.json().get("external", {}).get("google"))
    except Exception:
        enabled = False
    _providers_cache["google"] = (time.time() + _PROVIDERS_CACHE_SECONDS, enabled)
    return enabled


@app.get("/api/config")
def public_config():
    """Settings the browser needs to show the login screen (all public)."""
    return {"supabase_url": config.SUPABASE_URL, "supabase_publishable_key": config.SUPABASE_PUBLISHABLE_KEY,
            "google_enabled": bool(config.SUPABASE_URL) and _google_enabled()}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"email": user["email"], "is_admin": user["is_admin"], "usage": _usage(user)}


@app.get("/api/conversations")
def conversations(user: dict = Depends(current_user)):
    return store.list_conversations(user["id"])


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str, user: dict = Depends(current_user)):
    found = store.get_conversation(conversation_id, user["id"])
    if not found:
        raise HTTPException(404, "Conversation not found.")
    return {"id": found["id"], "title": found["title"],
            "turns": [_turn(plan) for plan in store.list_plans(conversation_id, user["id"])]}


def _turn(plan: dict) -> dict:
    return {
        "plan_id": plan["id"],
        "request": plan["request"],
        "reply": plan["reply"],
        "data": plan.get("tool_data", []),
        "issues": plan.get("issues", []),
        "feedback": {"rating": plan.get("rating"), "comment": plan.get("comment", ""),
                     "flags": plan.get("flags", [])},
    }


@app.post("/api/plans/{plan_id}/feedback")
def feedback(plan_id: str, body: FeedbackRequest, user: dict = Depends(current_user)):
    allowed = {"prices_wrong", "itinerary_confusing", "missing_info"}
    flags = [flag for flag in body.flags if flag in allowed]
    if not store.set_feedback(plan_id, user["id"], body.rating, body.comment.strip(), flags):
        raise HTTPException(404, "Plan not found.")
    return {"ok": True}


@app.post("/api/chat")
def chat(body: ChatRequest, user: dict = Depends(current_user)):
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "Please type a message.")
    limit = _limit_message(_usage(user))
    if limit:
        raise HTTPException(429, limit)

    if body.conversation_id:
        found = store.get_conversation(body.conversation_id, user["id"])
        if not found:
            raise HTTPException(404, "Conversation not found.")
        conversation_id, history = found["id"], found["messages"]
    else:
        conversation_id, history = None, []

    return StreamingResponse(_plan_stream(user, message, conversation_id, history),
                             media_type="application/x-ndjson")


def _plan_stream(user: dict, message: str, conversation_id: str | None, history: list):
    events: queue.Queue = queue.Queue()

    def on_event(event: dict) -> None:
        if event["type"] == "tool_started":
            events.put({"type": "progress", "status": "started", "tool": event["tool"],
                        "call_id": event["call_id"], "label": AGENT_LABELS.get(event["tool"], event["tool"])})
        elif event["type"] == "tool_finished":
            ok, summary = summarize(event["tool"], event["result"])
            events.put({"type": "progress", "status": "finished", "tool": event["tool"],
                        "call_id": event["call_id"], "ok": ok, "summary": summary})
        elif event["type"] == "fact_checking":
            events.put({"type": "progress", "status": "checking"})

    def work() -> None:
        global planner_client
        started = time.monotonic()
        messages = list(history)
        turn_start = len(messages)
        messages.append({"role": "user", "content": message})
        try:
            if planner_client is None:
                planner_client = get_client()
            reply = run_turn(planner_client, messages, on_event=on_event)
            results = tool_results(messages, turn_start)
            issues = check(reply, results)

            conv_id = conversation_id
            if conv_id:
                store.update_conversation(conv_id, messages)
            else:
                conv_id = store.create_conversation(user["id"], message[:80], messages)
            plan_id = store.save_plan({
                "user_id": user["id"], "user_email": user["email"], "conversation_id": conv_id,
                "request": message, "reply": reply,
                "tool_data": [list(r) for r in results], "issues": issues,
                "used_tools": bool(results), "duration_ms": int((time.monotonic() - started) * 1000),
            })
            events.put({"type": "result", "conversation_id": conv_id, "plan_id": plan_id, "reply": reply,
                        "data": [list(r) for r in results], "issues": issues, "usage": _usage(user)})
        except groq.RateLimitError:
            events.put({"type": "error", "message": (
                "The free AI service is at its limit right now. Please try again in a few minutes "
                "(or tomorrow, if today's allowance is used up).")})
        except groq.APIError:
            events.put({"type": "error", "message": "The AI service had a problem. Please try again."})
        except Exception:
            events.put({"type": "error", "message": "Something went wrong while planning. Please try again."})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (event := events.get()) is not None:
        yield json.dumps(event) + "\n"


@app.get("/api/admin/plans")
def admin_plans(_admin: dict = Depends(admin_user)):
    since = _start_of_today()
    return {"plans": store.admin_list_plans(),
            "site_plans_today": store.count_plans_since(since),
            "site_plans_limit": config.PLANS_PER_DAY_TOTAL}


# Serve the built website (web/dist) when it exists — a production-like
# local run on one port. During development, Vite serves it instead.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str):
        target = _DIST / path
        if path and target.is_file() and _DIST in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")
