"""Admin-editable agent prompts (Admin Control Panel — see TASKS.md).

Each agent's prompt is still a hardcoded Python string constant, which stays the source of
truth for the *default* — this module only adds an optional DB-backed override on top, read
fresh on every call (same "live toggle, not baked in at import time" pattern as
llm_router.py's get_speed_profile()). An empty `agent_prompts` table changes nothing.

Not every agent's prompt goes through this: `planner.py` (two templates, PLANNER_INIT/
PLANNER_NEXT) and `writer.py` (a domain-pack-composed template) build their prompts from
more than one hardcoded piece each, so a single free-text override doesn't safely cover
them — left on their hardcoded constants for this pass, callable out as a follow-up if the
demo calls for it.
"""
import logging

from db import supabase

logger = logging.getLogger(__name__)


def get_prompt(agent_name: str, default_text: str) -> str:
    """Returns the admin-edited prompt for `agent_name` if one exists, else `default_text`
    unchanged. Fails closed to the default on any DB error — a Postgres hiccup should never
    turn into every pipeline run using an empty prompt."""
    try:
        row = supabase.table("agent_prompts").select("prompt_text").eq("agent_name", agent_name).execute()
        return row.data[0]["prompt_text"] if row.data else default_text
    except Exception:
        logger.exception(f"Failed to read prompt override for '{agent_name}' — using default")
        return default_text
