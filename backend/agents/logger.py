"""
Append-only activity log helper for DS-STAR pipeline visibility.

Each agent calls log_event() once with a human-readable message and optional
metadata. Entries are stored as a JSONB array in tasks.logs and polled by
the frontend every 2 seconds alongside the task status.
"""

import json
import logging
from datetime import datetime, timezone
from db import supabase

logger = logging.getLogger(__name__)


def log_event(
    task_id: str,
    agent: str,
    message: str,
    status: str = "info",   # "info" | "success" | "error" | "running"
    meta: dict = None,
) -> None:
    """Append one log entry to tasks.logs for the given task_id."""
    entry = {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "agent":   agent,
        "message": message,
        "status":  status,
        **(meta or {}),
    }

    try:
        # Atomic at the database level (see migrations/2026-08-03_atomic_log_append.sql)
        # — a single UPDATE ... logs = logs || entry, no read-modify-write window in this
        # process. Two log_event() calls for the same task_id are genuinely concurrent in
        # practice (a user's Stop/Pause request on the main event loop vs. the graph's
        # currently-running node logging from run_graph's background thread), and the old
        # select-then-append-then-update here would silently drop whichever write lost
        # the race.
        supabase.rpc("append_task_log", {"p_task_id": task_id, "p_entry": entry}).execute()
    except Exception as e:
        logger.warning(f"append_task_log RPC failed, falling back to read-modify-write: {e}")
        _append_log_entry_read_modify_write(task_id, entry)


def _append_log_entry_read_modify_write(task_id: str, entry: dict) -> None:
    """Fallback for an environment where migrations/2026-08-03_atomic_log_append.sql
    hasn't been applied yet — same race window the migration exists to close, kept only
    so logging degrades to the old (imperfect but functional) behavior instead of losing
    the entry outright."""
    try:
        res = supabase.table("tasks").select("logs").eq("task_id", task_id).execute()
        current = []
        if res.data:
            raw = res.data[0].get("logs") or []
            if isinstance(raw, str):
                try:
                    current = json.loads(raw)
                except Exception:
                    current = []
            elif isinstance(raw, list):
                current = raw

        current.append(entry)
        supabase.table("tasks").update({"logs": current}).eq("task_id", task_id).execute()
    except Exception as e:
        # Never let logging kill the pipeline
        logger.warning(f"failed to write log entry: {e}")
