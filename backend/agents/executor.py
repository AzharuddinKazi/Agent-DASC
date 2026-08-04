import logging
import subprocess
import tempfile
import time
import os
import uuid

from db import supabase
from agents.logger import log_event
from agents.state import TaskState
from agents.cancellation import is_cancelled, is_paused, TaskCancelled, TaskPaused
from agents.script_repair import repair_fstring_format_specs
from agents.sandbox_security import docker_security_args
from agents.error_sanitizer import summarize_script_failure

logger = logging.getLogger(__name__)

DOCKER_TIMEOUT_S = 120

# How often execute_script checks for a Stop/Pause request while the container runs.
# Without this, Stop/Pause only take effect at the next node boundary — fine for
# LLM-call nodes (seconds), but this is the one node that can legitimately block up to
# DOCKER_TIMEOUT_S on a single call, which would make them feel broken for up to two
# minutes.
POLL_INTERVAL_S = 0.5


def execute_script(script: str, task_id: str | None = None) -> tuple:
    script = repair_fstring_format_specs(script)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    # A named (not anonymous) container is what makes it possible to `docker kill` this
    # specific run from outside the blocking subprocess call below.
    container_name = f"dsstar-exec-{uuid.uuid4().hex[:12]}"
    proc = None
    try:
        proc = subprocess.Popen(
            [
                "docker", "run", "--rm",
                "--name", container_name,
                "--network=none",
                "--memory=2g",
                *docker_security_args(),
                "-v", f"{os.getenv('DSSTAR')}/data:/workspace/data:ro",
                "-v", f"{script_path}:/workspace/scripts/step.py:ro",
                "dsstar-sandbox:latest",
                "python3", "/workspace/scripts/step.py"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        deadline = time.monotonic() + DOCKER_TIMEOUT_S
        while True:
            try:
                # Polling via repeated communicate(timeout=...) calls is the documented-safe
                # pattern for this (stdlib subprocess docs) — no data is lost between polls.
                stdout, stderr = proc.communicate(timeout=POLL_INTERVAL_S)
                break
            except subprocess.TimeoutExpired:
                if task_id and is_cancelled(task_id):
                    subprocess.run(["docker", "kill", container_name], capture_output=True)
                    proc.wait(timeout=5)
                    raise TaskCancelled(f"Task {task_id} was stopped by the user")
                if task_id and is_paused(task_id):
                    # Restart-the-step semantics (not a true docker-pause/unpause freeze):
                    # kill this attempt, resume later re-runs the whole step from scratch.
                    subprocess.run(["docker", "kill", container_name], capture_output=True)
                    proc.wait(timeout=5)
                    raise TaskPaused(f"Task {task_id} was paused by the user")
                if time.monotonic() > deadline:
                    subprocess.run(["docker", "kill", container_name], capture_output=True)
                    proc.wait(timeout=5)
                    raise subprocess.TimeoutExpired(cmd="docker run", timeout=DOCKER_TIMEOUT_S)

        # 3000 chars was truncating mid-JSON on the Finalizer's structured output
        # whenever a result had more than a few table rows, producing invalid JSON
        # that the frontend then fell back to rendering as raw text.
        return stdout[:50_000], stderr[:2_000], proc.returncode
    finally:
        os.unlink(script_path)


def executor(state: TaskState) -> dict:

    supabase.table("tasks").update({"current_agent": "executor"}).eq("task_id", state["task_id"]).execute()

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "executor",
              f"{label}Running script in Docker sandbox · Round {state['current_round']}",
              "running",
              {"round": state["current_round"],
               **({"sub_q_idx": current_sub_idx + 1, "sub_q_total": len(sub_questions)} if sub_questions else {})})

    stdout, stderr, exit_code = execute_script(state["current_script"], state["task_id"])
    logger.info(f"Exit code: {exit_code}")
    if stdout:
        logger.info(f"Output: {stdout}")
    if stderr and exit_code != 0:
        logger.error(f"Error: {stderr[:200]}")

    if exit_code == 0:
        log_event(state["task_id"], "executor",
                  f"{label}Script executed successfully · Round {state['current_round']}",
                  "success", {"round": state["current_round"]})
    else:
        # Sanitized for the same reason as finalizer.py's final_result — this message and
        # meta are served through GET /api/v1/get_task via tasks.logs, so the first N raw
        # characters of a traceback (internal container file paths, library internals,
        # and usually just the unhelpful "Traceback (most recent call last):" header
        # rather than the actual error) shouldn't be what a caller sees. Full stderr is
        # still in the `logger.error` call above for server-side diagnostics.
        failure_summary = summarize_script_failure(stderr)
        log_event(state["task_id"], "executor",
                  f"{label}Script failed · {failure_summary}",
                  "error", {"round": state["current_round"], "error_summary": failure_summary})

    return {
        "execution_result": stdout if exit_code == 0 else stderr,
        "exit_code":        exit_code,
        "debug_attempts":   0 if exit_code == 0 else state.get("debug_attempts", 0) + 1,
    }
