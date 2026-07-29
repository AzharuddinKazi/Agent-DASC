from agents.state import TaskState
from agents.code_fences import strip_code_fences
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
import logging, os
router = LLMRouter()
logger = logging.getLogger(__name__)

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
- SyntaxError from a nested f-string with escaped quotes inside the expression part
  (e.g. f"...{{', '.join([f'{{row[\"X\"]}}' for _, row in df.iterrows()])}}...") — fix
  by building the inner strings in a separate variable/list first, then interpolating
  that plain variable into the outer f-string instead of nesting.
- No error output at all (empty error message, non-zero exit): the process was almost
  certainly killed for exceeding the sandbox's 2GB memory limit — always add
  nrows=10000 to any pd.read_csv call, especially before an operation that multiplies
  row count (pd.melt, wide-to-long reshapes, merges/joins).

Provide the complete fixed Python script.
There should be no additional headings or text in your response."""


def debugger(state: TaskState) -> dict:

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

    result       = router.complete(agent="debugger", prompt=prompt, task_id=state["task_id"])
    fixed_script = strip_code_fences(result["text"].strip())

    logger.info("Fixed script generated")

    return {"current_script": fixed_script}