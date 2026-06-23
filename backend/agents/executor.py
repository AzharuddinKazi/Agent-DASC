import subprocess
import tempfile
import os

from db import supabase
from agents.logger import log_event
from agents.state import TaskState

def execute_script(script: str) -> tuple:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=2g",
                "-v", f"{os.getenv('DSSTAR')}/data:/workspace/data:ro",
                "-v", f"{script_path}:/workspace/scripts/step.py:ro",
                "dsstar-sandbox:latest",
                "python3", "/workspace/scripts/step.py"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout[:3000], result.stderr[:500], result.returncode
    finally:
        os.unlink(script_path)

def executor(state: TaskState) -> dict:

    # supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    supabase.table("tasks").update({"current_agent": "executor"}).eq("task_id", state["task_id"]).execute()

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "executor",
              f"{label}Running script in Docker sandbox · Round {state['current_round']}",
              "running",
              {"round": state["current_round"],
               **({"sub_q_idx": current_sub_idx + 1, "sub_q_total": len(sub_questions)} if sub_questions else {})})

    stdout, stderr, exit_code = execute_script(state["current_script"])
    print(f"[Executor] Exit code: {exit_code}")
    if stdout:
        print(f"[Executor] Output: {stdout}")
    if stderr and exit_code != 0:
        print(f"[Executor] Error: {stderr[:200]}")

    if exit_code == 0:
        log_event(state["task_id"], "executor",
                  f"{label}Script executed successfully · Round {state['current_round']}",
                  "success", {"round": state["current_round"]})
    else:
        log_event(state["task_id"], "executor",
                  f"{label}Script failed · {stderr[:120]}",
                  "error", {"round": state["current_round"], "stderr": stderr[:300]})

    return {
        "execution_result": stdout if exit_code == 0 else stderr,
        "exit_code":        exit_code,
        "debug_attempts":   0 if exit_code == 0 else state.get("debug_attempts", 0) + 1,
    }