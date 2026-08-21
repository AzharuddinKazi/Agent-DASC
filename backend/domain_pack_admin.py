"""Admin CRUD for the domain pack catalog (`domain_pack_configs`) — create/update/delete,
the operations main.py's browsing/activation routes don't provide (those are read-only plus
activate/deactivate). Mirrors domain_pack.py's table access but doesn't need its
fail-closed-to-generic-defaults behavior: these are direct admin writes, not agent-facing
reads on the pipeline's hot path, so letting an error surface as a 500 is correct here.
"""

from db import supabase

# Columns an admin write is allowed to touch — mirrors
# backend/migrations/2026-08-20_domain_pack_catalog_columns.sql's catalog columns plus the
# pre-existing prompt-config columns. `pack_id` is deliberately excluded: it's the row's
# key, set once at creation, never rewritten by an update.
_EDITABLE_FIELDS = {
    "name", "description", "tags", "dataset_generator", "example_question",
    "report_persona", "report_classification", "subquestion_dimensions",
}


def create_pack(pack_id: str, data: dict) -> dict:
    row = {"pack_id": pack_id, **{k: v for k, v in data.items() if k in _EDITABLE_FIELDS}}
    result = supabase.table("domain_pack_configs").insert(row).execute()
    return result.data[0]


def update_pack(pack_id: str, data: dict) -> dict | None:
    fields = {k: v for k, v in data.items() if k in _EDITABLE_FIELDS}
    result = supabase.table("domain_pack_configs").update(fields).eq("pack_id", pack_id).execute()
    return result.data[0] if result.data else None


def delete_pack(pack_id: str) -> None:
    supabase.table("domain_pack_configs").delete().eq("pack_id", pack_id).execute()
    # If the deleted pack was the globally active one, fall back to "generic" so
    # domain_pack.get_active_pack_config() doesn't keep pointing at a now-missing row —
    # its own fallback only kicks in on a *query* returning empty, not proactively.
    active = supabase.table("app_settings").select("value").eq("key", "active_domain_pack").execute()
    if active.data and active.data[0]["value"] == pack_id:
        supabase.table("app_settings").upsert({"key": "active_domain_pack", "value": "generic"}).execute()
