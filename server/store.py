"""Where the website keeps its data: conversations, plans, and feedback.

`SupabaseStore` talks to Supabase's Postgres through its REST API using the
server-only secret key (tables have row-level security on and no public
policies, so browsers can't read them directly). `MemoryStore` has the same
methods and is used by the tests.
"""

import datetime as dt
import uuid

import httpx

from server import config


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SupabaseStore:
    def __init__(self, url: str = "", key: str = ""):
        self.base = f"{url or config.SUPABASE_URL}/rest/v1"
        key = key or config.SUPABASE_SECRET_KEY
        self.headers = {"apikey": key}
        # New-style secret keys (sb_secret_...) go in `apikey` only; legacy
        # service_role keys are JWTs and also need the Authorization header.
        if not key.startswith("sb_"):
            self.headers["Authorization"] = f"Bearer {key}"

    def _request(self, method: str, table: str, *, params=None, json=None, prefer: str = ""):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        response = httpx.request(method, f"{self.base}/{table}", params=params, json=json,
                                 headers=headers, timeout=15)
        response.raise_for_status()
        return response

    def _count(self, params: dict) -> int:
        response = self._request("GET", "plans", params={"select": "id", "limit": 1, **params},
                                 prefer="count=exact")
        # Content-Range: 0-0/5  (or */0 when empty)
        return int(response.headers.get("content-range", "*/0").rsplit("/", 1)[1])

    def count_plans_since(self, since: str, user_id: str | None = None) -> int:
        params = {"created_at": f"gte.{since}", "used_tools": "is.true"}
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        return self._count(params)

    def count_messages_since(self, since: str, user_id: str) -> int:
        return self._count({"created_at": f"gte.{since}", "user_id": f"eq.{user_id}"})

    def create_conversation(self, user_id: str, title: str, messages: list) -> str:
        rows = self._request("POST", "conversations", prefer="return=representation", json={
            "user_id": user_id, "title": title, "messages": messages,
        }).json()
        return rows[0]["id"]

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None:
        rows = self._request("GET", "conversations", params={
            "id": f"eq.{conversation_id}", "user_id": f"eq.{user_id}", "select": "id,title,messages",
        }).json()
        return rows[0] if rows else None

    def update_conversation(self, conversation_id: str, messages: list) -> None:
        self._request("PATCH", "conversations", params={"id": f"eq.{conversation_id}"},
                      json={"messages": messages, "updated_at": _now()})

    def list_conversations(self, user_id: str) -> list:
        return self._request("GET", "conversations", params={
            "user_id": f"eq.{user_id}", "select": "id,title,updated_at", "order": "updated_at.desc", "limit": 50,
        }).json()

    def save_plan(self, record: dict) -> str:
        rows = self._request("POST", "plans", prefer="return=representation", json=record).json()
        return rows[0]["id"]

    def list_plans(self, conversation_id: str, user_id: str) -> list:
        return self._request("GET", "plans", params={
            "conversation_id": f"eq.{conversation_id}", "user_id": f"eq.{user_id}",
            "select": "id,request,reply,tool_data,issues,rating,comment,flags,created_at",
            "order": "created_at.asc",
        }).json()

    def set_feedback(self, plan_id: str, user_id: str, rating: int | None, comment: str, flags: list) -> bool:
        rows = self._request("PATCH", "plans", prefer="return=representation",
                             params={"id": f"eq.{plan_id}", "user_id": f"eq.{user_id}"},
                             json={"rating": rating, "comment": comment, "flags": flags,
                                   "feedback_at": _now()}).json()
        return bool(rows)

    def admin_list_plans(self, limit: int = 200) -> list:
        return self._request("GET", "plans", params={
            "select": "id,user_email,request,reply,issues,used_tools,duration_ms,rating,comment,flags,created_at",
            "order": "created_at.desc", "limit": limit,
        }).json()


class MemoryStore:
    """In-process stand-in with the same methods, for tests."""

    def __init__(self):
        self.conversations: dict = {}
        self.plans: dict = {}

    def count_plans_since(self, since: str, user_id: str | None = None) -> int:
        return sum(1 for p in self.plans.values()
                   if p["created_at"] >= since and p["used_tools"] and (user_id is None or p["user_id"] == user_id))

    def count_messages_since(self, since: str, user_id: str) -> int:
        return sum(1 for p in self.plans.values() if p["created_at"] >= since and p["user_id"] == user_id)

    def create_conversation(self, user_id: str, title: str, messages: list) -> str:
        conversation_id = str(uuid.uuid4())
        self.conversations[conversation_id] = {"id": conversation_id, "user_id": user_id, "title": title,
                                               "messages": messages, "updated_at": _now()}
        return conversation_id

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None:
        conversation = self.conversations.get(conversation_id)
        return conversation if conversation and conversation["user_id"] == user_id else None

    def update_conversation(self, conversation_id: str, messages: list) -> None:
        self.conversations[conversation_id].update(messages=messages, updated_at=_now())

    def list_conversations(self, user_id: str) -> list:
        rows = [c for c in self.conversations.values() if c["user_id"] == user_id]
        return [{k: c[k] for k in ("id", "title", "updated_at")}
                for c in sorted(rows, key=lambda c: c["updated_at"], reverse=True)]

    def save_plan(self, record: dict) -> str:
        plan_id = str(uuid.uuid4())
        self.plans[plan_id] = {"id": plan_id, "created_at": _now(), "rating": None, "comment": "",
                               "flags": [], **record}
        return plan_id

    def list_plans(self, conversation_id: str, user_id: str) -> list:
        return sorted((p for p in self.plans.values()
                       if p["conversation_id"] == conversation_id and p["user_id"] == user_id),
                      key=lambda p: p["created_at"])

    def set_feedback(self, plan_id: str, user_id: str, rating: int | None, comment: str, flags: list) -> bool:
        plan = self.plans.get(plan_id)
        if not plan or plan["user_id"] != user_id:
            return False
        plan.update(rating=rating, comment=comment, flags=flags)
        return True

    def admin_list_plans(self, limit: int = 200) -> list:
        return sorted(self.plans.values(), key=lambda p: p["created_at"], reverse=True)[:limit]
