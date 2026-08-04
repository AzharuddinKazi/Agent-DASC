"""Shared `docker run` hardening flags for every sandbox invocation that executes
LLM-generated code (agents/analyzer.py's file-profiling script, agents/executor.py's
main script execution) — one place so both stay in sync rather than drifting.

The image already runs as a non-root `app` user (sandbox/Dockerfile) with
`--network=none` and a `--memory` cap at each call site. This adds the hardening the
audit flagged as missing: a CPU share so one script can't starve the host, a pid limit
against fork bombs, a read-only root filesystem so a script can't persist anything
outside its own run, and dropping every Linux capability the container never needs
(it isn't root, doesn't bind privileged ports, doesn't touch devices).
"""
import os

SANDBOX_CPUS = os.getenv("SANDBOX_CPUS", "2")
SANDBOX_PIDS_LIMIT = os.getenv("SANDBOX_PIDS_LIMIT", "128")

# A read-only rootfs means `python3` has nowhere to write even its own transient state
# (matplotlib's config/cache dir, any library that shells out to a tempfile) unless
# something is explicitly writable — a small tmpfs at /tmp covers that without opening
# up the rest of the filesystem. Generated scripts only ever print to stdout (see the
# Analyzer/Coder/Finalizer prompts) — none of them are expected to persist files, so this
# tmpfs isn't a workspace, just enough scratch space for well-behaved libraries.
def docker_security_args() -> list[str]:
    return [
        "--cpus", SANDBOX_CPUS,
        "--pids-limit", SANDBOX_PIDS_LIMIT,
        "--read-only",
        "--tmpfs", "/tmp:size=256m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
    ]
