"""
Append-only activity log helper for DS-STAR pipeline visibility.

Each agent calls log_event() once with a human-readable message and optional
metadata. Entries are stored as a JSONB array in tasks.logs and polled by
the frontend every 2 seconds alongside the task status.
"""

import json
from datetime import datetime, timezone
from db import supabase


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
        print(f"[logger] WARNING: failed to write log entry: {e}")
