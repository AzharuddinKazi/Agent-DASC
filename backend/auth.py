"""Real Google OAuth login (see TASKS.md "Google OAuth login + Admin Control Panel").

Replaces the single-fixed-local-user stub this file held during the auth-removal pass.
No GoTrue/Supabase Auth re-introduced — the frontend gets Google's identity token directly
via Google Identity Services (no OAuth redirect dance), this module verifies it server-side
and issues its own signed session cookie. No `sessions` table: the cookie itself carries
`user_id`/`exp`, and every request re-reads the `users` row by that id anyway (needed to
catch a ban applied mid-session and to compute `is_admin` freshly), so a separate session
store would just be a second source of truth for state already re-fetched every request.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from db import supabase

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")
SESSION_COOKIE_NAME = "session"
SESSION_TTL_DAYS = 30

# Open sign-up (any Google account) per the user's explicit choice — admin status is what's
# gated, not login itself. Comma-separated, matches the old ADMIN_EMAILS convention.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
}


@dataclass(frozen=True)
class AuthUser:
    id: str
    # None for a guest (name-only) account — see auth_guest in main.py. Never None for a
    # Google account (verified at sign-in time).
    email: str | None
    name: str | None = None
    picture_url: str | None = None
    is_admin: bool = False


def verify_google_id_token(credential: str) -> dict:
    """Verifies a Google Identity Services credential JWT against Google's own public keys
    — no secret round-trip needed for verification itself, just the Client ID this token
    was issued for. Raises ValueError (via the underlying library) on an invalid/expired/
    wrong-audience token; callers turn that into a 401."""
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID is not set — see backend/.env.example. Create one at "
            "https://console.cloud.google.com/apis/credentials (OAuth client ID, Web "
            "application, authorized JS origin matching the frontend's URL)."
        )
    return google_id_token.verify_oauth2_token(
        credential, google_requests.Request(), GOOGLE_CLIENT_ID
    )


def issue_session_cookie(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    }
    return jwt.encode(payload, SESSION_SECRET_KEY, algorithm="HS256")


def _read_session_cookie(token: str) -> str | None:
    """Returns the user_id encoded in a valid, unexpired session cookie, or None — never
    raises, so callers can treat "bad cookie" and "no cookie" identically (both mean
    "not logged in")."""
    try:
        payload = jwt.decode(token, SESSION_SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def _load_user_row(user_id: str) -> dict | None:
    resp = supabase.table("users").select("*").eq("id", user_id).execute()
    return resp.data[0] if resp.data else None


async def get_current_user(request: Request) -> AuthUser:
    """Reads the session cookie, verifies it, and re-loads the user row fresh from the DB
    on every call — not just decoded-and-trusted from the JWT — so a ban applied mid-session
    (or an admin-allowlist email removed from ADMIN_EMAILS) takes effect on this user's very
    next request, not only after their session expires."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = _read_session_cookie(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Not signed in")

    row = _load_user_row(user_id)
    if not row:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    if row["is_banned"]:
        raise HTTPException(status_code=403, detail="This account has been banned")

    return AuthUser(
        id=row["id"], email=row["email"], name=row.get("name"),
        picture_url=row.get("picture_url"), is_admin=row["is_admin"],
    )


async def get_current_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
