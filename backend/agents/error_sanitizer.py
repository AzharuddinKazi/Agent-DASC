"""Keeps raw tracebacks/exception detail out of what gets persisted as a task's
user-facing final_result and served back through the API — full detail is never lost,
it's just routed to the actual observability channels (logger.exception, Sentry) instead
of the primary response body every caller of GET /api/v1/get_task/{id} sees.
"""

GENERIC_INFRASTRUCTURE_ERROR = (
    "The analysis failed due to an unexpected internal error. This has been logged — "
    "please try again or start a new analysis."
)


def summarize_script_failure(stderr: str) -> str:
    """Reduces a raw Python traceback from a generated script (internal container file
    paths, stack frames, library internals) down to just its final "ExceptionType:
    message" line — the part that's actually informative to the person who submitted the
    query — instead of dumping the whole thing into final_result. The full stderr is
    still captured server-side (see executor.py/finalizer.py's own logger calls)."""
    lines = [l for l in (stderr or "").strip().splitlines() if l.strip()]
    if not lines:
        return "The generated script failed with no error output."
    return lines[-1]
