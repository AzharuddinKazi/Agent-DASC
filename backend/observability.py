"""Operational logging + error tracking setup, called once at startup (see main.py).

Distinct from agents/logger.py's log_event(), which is user-facing pipeline *progress*
stored per-task in Supabase and polled by the frontend. This module is for engineers:
structured stdout logs and (optionally) Sentry.
"""

import json
import logging
import os
import sys
import traceback


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level":  record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(entry)


def configure_logging():
    """Root logger → stdout, JSON-formatted. Standard for a containerized app: write
    structured lines to stdout and let the container runtime/aggregator collect them,
    rather than writing to a file inside an ephemeral container.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def configure_error_tracking():
    """Initializes Sentry if SENTRY_DSN is set; otherwise a deliberate no-op. Code that
    calls sentry_sdk.capture_exception() elsewhere is always safe to call regardless of
    whether this ran — the SDK no-ops when it was never initialized.
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(),
            # ERROR-level log records become Sentry events too, since some errors are
            # logged without an exception object (e.g. agents/logger.py's own failure path).
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
    )
