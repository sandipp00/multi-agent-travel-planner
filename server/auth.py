"""Who is calling: verify the Supabase login token sent by the browser.

The browser signs in with Supabase (email/password or Google) and sends its
access token as `Authorization: Bearer <token>`. We ask Supabase who that
token belongs to — so we never handle passwords or signing keys ourselves.
"""

import time

import httpx
from fastapi import Header, HTTPException

from server import config

# Token -> (expires_at, user). Avoids one Supabase round trip per request.
_CACHE_SECONDS = 60
_cache: dict = {}


def _lookup_user(token: str) -> dict | None:
    cached = _cache.get(token)
    if cached and cached[0] > time.time():
        return cached[1]
    try:
        response = httpx.get(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={"apikey": config.SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Couldn't reach the login service. Please try again.")
    if response.status_code != 200:
        return None
    data = response.json()
    email = (data.get("email") or "").lower()
    user = {
        "id": data["id"],
        "email": email,
        # Email sign-ups must click the link Supabase emails them first.
        "email_confirmed": bool(data.get("email_confirmed_at") or data.get("confirmed_at")),
        "is_admin": email in config.ADMIN_EMAILS,
    }
    _cache[token] = (time.time() + _CACHE_SECONDS, user)
    return user


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: the signed-in, email-confirmed user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.")
    user = _lookup_user(authorization.split(" ", 1)[1].strip())
    if user is None:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    if not user["email_confirmed"]:
        raise HTTPException(403, "Please confirm your email address first — check your inbox.")
    return user


def admin_user(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    if not user["is_admin"]:
        raise HTTPException(403, "Admins only.")
    return user
