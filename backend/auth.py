import os
from fastapi import Depends, Header, HTTPException
from supabase import create_client

_anon_client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

# Admin allowlist — a comma-separated list of emails in ADMIN_EMAILS, not a role or claim
# on the Supabase user record. This app has no broader RBAC system; an allowlist is the
# simplest thing that's actually correct for "who can reach the admin API/UI" without
# inventing a whole roles table for one use. Re-read from the environment on every call
# rather than cached at import time, so updating it (e.g. via docker-compose env, or an
# .env reload in dev) doesn't need a process restart to take effect... except uvicorn
# itself still needs a restart to pick up a changed .env either way (load_dotenv() only
# runs once at startup) — this just avoids adding a *second* reason a restart would be
# needed on top of that.
def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}


async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        resp = _anon_client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not resp or not resp.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return resp.user


async def get_current_admin(user=Depends(get_current_user)):
    """Same bearer-token validation as get_current_user, plus an ADMIN_EMAILS allowlist
    check. An unset/empty ADMIN_EMAILS means no one is an admin (fails closed) rather
    than everyone being one."""
    if (user.email or "").lower() not in _admin_emails():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
