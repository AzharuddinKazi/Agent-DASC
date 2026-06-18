import subprocess
import tempfile
import os
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
    stdout, stderr, exit_code = execute_script(state["current_script"])
    print(f"[Executor] Exit code: {exit_code}")
    if stdout:
        print(f"[Executor] Output: {stdout}")
    if stderr and exit_code != 0:
        print(f"[Executor] Error: {stderr[:200]}")
    return {
        "execution_result": stdout if exit_code == 0 else stderr,
        "exit_code":        exit_code,
        "debug_attempts":   0 if exit_code == 0 else state.get("debug_attempts", 0) + 1,
    }