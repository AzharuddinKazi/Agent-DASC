"""Recursively replaces non-finite floats (NaN/Infinity/-Infinity) with None.

Python's `json` module accepts these as valid tokens on both dump and load (unlike the
JSON spec), so an LLM-generated script's `json.dumps()` output can round-trip through
`json.loads()` here without ever raising — the resulting dict still holds `float('nan')`
objects, which re-serialize back into the same non-spec-compliant `NaN` token. That
token is what the frontend's spec-compliant `JSON.parse` then rejects, losing the
structured view (table/chart/key findings) for an otherwise-successful result.
"""
import math
import re
from typing import Any

_NON_FINITE_TOKEN = re.compile(r"\bNaN\b|\bInfinity\b")


def sanitize_json_floats(value: Any) -> Any:
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, dict):
        return {k: sanitize_json_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json_floats(v) for v in value]
    return value


def has_non_finite_token(raw_json_text: str) -> bool:
    """Cheap pre-check so callers can skip re-serializing (and reformatting) JSON that
    never had a NaN/Infinity token in the first place — a false positive from one
    appearing inside a string value just costs an unnecessary but harmless re-dump."""
    return bool(_NON_FINITE_TOKEN.search(raw_json_text))
