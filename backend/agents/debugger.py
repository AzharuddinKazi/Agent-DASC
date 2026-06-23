from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
import os
router = LLMRouter()

DEBUGGER_PROMPT = """# Given data files (available at /workspace/data/):
{filenames}

# Code with an error:
[python]
{code}
[/python]

# Error:
{bug}

# Your task
Fix the error in the code above.

# Common fixes to check first:
- File path errors: always use /workspace/data/filename, never just filename
- CSV separator: try comma first, then semicolon, then tab
- Shell commands (!head, !cat) are not allowed — replace with pandas or open()
- Import errors: only pandas, numpy, matplotlib, openpyxl, scipy, sklearn are available

Provide the complete fixed Python script.
There should be no additional headings or text in your response."""


def debugger(state: TaskState) -> dict:

    # supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    supabase.table("tasks").update({"current_agent": "debugger"}).eq("task_id", state["task_id"]).execute()

    attempt = state.get("debug_attempts", 0)
    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "debugger",
              f"{label}Debug attempt {attempt} — analysing traceback and patching script",
              "error",
              {"attempt": attempt, "round": state.get("current_round", 0)})

    summaries      = state["data_descriptions"]
    current_script = state["current_script"]
    error          = state["execution_result"]

    filenames = "\n".join(summaries.keys())

    prompt = DEBUGGER_PROMPT.format(
        filenames=filenames,
        code=current_script,
        bug=error
    )

    result       = router.complete(agent="debugger", prompt=prompt)
    fixed_script = result["text"].strip()

    if fixed_script.startswith("```"):
        lines        = fixed_script.split("\n")
        fixed_script = "\n".join(lines[1:-1])

    print(f"[Debugger] Fixed script generated")

    return {"current_script": fixed_script}