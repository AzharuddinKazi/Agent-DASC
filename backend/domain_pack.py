"""
Domain configuration for report generation — DB-backed.

The core DS-STAR pipeline (Analyzer/Planner/Coder/Debugger/Verifier/Router) is already
fully domain-agnostic — it reasons from whatever data and question it's given. This module
provides the two places that used to hardcode a specific domain (financial-crime
compliance): the Writer's report persona, and an optional topic hint for the sub-question
generator, plus the domain pack's knowledge-base scope for the Planner.

The active pack is switchable at runtime from the Domain Packs page — no file edit, no
restart. `app_settings.active_domain_pack` names the active row in `domain_pack_configs`;
"generic" is the always-present default. See domain_packs/fraud_aml_example.py for a
preserved historical reference of the original CBUAE/AML deployment this app was first
built for (its values were used once, to seed the generic/fraud-aml rows in the database).
"""

from db import supabase

_GENERIC_ID = "generic"


def get_active_pack_config(override_pack_id: str | None = None) -> dict:
    """Reads a domain pack's config from the database.

    Args:
        override_pack_id: when given, use this pack instead of the globally active one —
            lets a single task submission pin its own pack without changing the
            deployment-wide setting other users/tasks see. None (the default) preserves
            the original behaviour of reading `app_settings.active_domain_pack`.

    Returns:
        A dict with report_persona, report_classification, subquestion_dimensions, and
        pack_id (None when the generic default is active, matching the pre-DB PACK_ID
        semantics). Falls back to hardcoded generic defaults if the database is
        unreachable or the active row is somehow missing, so a config issue degrades to
        "no domain pack" rather than crashing the pipeline.
    """
    try:
        if override_pack_id:
            pack_id = override_pack_id
        else:
            settings = supabase.table("app_settings").select("value").eq("key", "active_domain_pack").execute()
            pack_id = (settings.data[0]["value"] if settings.data else None) or _GENERIC_ID

        row = supabase.table("domain_pack_configs").select("*").eq("pack_id", pack_id).execute()
        if not row.data:
            pack_id = _GENERIC_ID
            row = supabase.table("domain_pack_configs").select("*").eq("pack_id", _GENERIC_ID).execute()
        cfg = row.data[0]
        return {
            "pack_id":                 None if pack_id == _GENERIC_ID else pack_id,
            "report_persona":          cfg["report_persona"],
            "report_classification":   cfg["report_classification"],
            "subquestion_dimensions":  cfg["subquestion_dimensions"] or [],
        }
    except Exception:
        return {
            "pack_id":                None,
            "report_persona":         "You are a senior data analyst writing a report for a business stakeholder.",
            "report_classification":  None,
            "subquestion_dimensions": [],
        }
