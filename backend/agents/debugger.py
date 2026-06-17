from agents.state import TaskState
from llm_router import LLMRouter

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