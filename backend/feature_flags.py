"""Runtime feature flags — DB-backed via app_settings, the same live-toggle pattern
already used for llm_speed_profile and active_domain_pack (see llm_router.py /
domain_pack.py): a flag flips the very next request, no deploy or restart, and always
falls back to its documented default if never toggled or the DB is unreachable.

Add a new flag by adding its name + default to KNOWN_FEATURES — GET/POST
/api/v1/admin/features picks it up automatically, nothing else needs to change for it to
show up there. Actually gating a feature is still the caller's job: check is_enabled()
at whatever the feature's real choke point is (e.g. domain_pack.get_active_pack_config()
for "domain_packs" — see that module for why that's the right single place, not each
individual endpoint).
"""

from db import supabase

# name -> default state (used when a flag has never been toggled, or the DB is
# unreachable — degrades to this rather than silently breaking a feature no one meant
# to touch).
KNOWN_FEATURES = {
    "domain_packs": True,
    # Off by default — exposes a read-only "what data is already loaded" view to every
    # signed-in user (not just admins), for demoing the app to people who'd otherwise have
    # to be told by hand what's in it. See main.py's demo_data / demo_documents.
    "demo_mode": False,
}


def _key(name: str) -> str:
    return f"feature:{name}"


def is_enabled(name: str) -> bool:
    default = KNOWN_FEATURES.get(name, True)
    try:
        row = supabase.table("app_settings").select("value").eq("key", _key(name)).execute()
        if not row.data:
            return default
        return row.data[0]["value"] == "true"
    except Exception:
        return default


def set_enabled(name: str, enabled: bool) -> None:
    if name not in KNOWN_FEATURES:
        raise ValueError(f"Unknown feature: {name}")
    supabase.table("app_settings").upsert({
        "key": _key(name), "value": "true" if enabled else "false",
    }).execute()


def all_flags() -> dict[str, bool]:
    return {name: is_enabled(name) for name in KNOWN_FEATURES}
