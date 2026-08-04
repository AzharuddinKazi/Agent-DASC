import json
import logging
from agents.state import TaskState
from agents.executor import execute_script
from agents.debugger import DEBUGGER_PROMPT
from agents.code_fences import strip_code_fences
from agents.logger import log_event
from agents.schemas import FinalizerOutput, validate_and_log
from agents.error_sanitizer import summarize_script_failure
from agents.prompt_safety import format_file_summaries
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()
logger = logging.getLogger(__name__)

# Unlike the main planner→coder→executor loop, the Finalizer's script was previously
# one-shot — a bad script (e.g. a hallucinated row/id lookup) failed the whole task with
# no recovery. Give it the same bounded self-debug the main loop gets, reusing the
# debugger's prompt/pattern rather than routing back through the graph.
MAX_FINALIZER_DEBUG_ATTEMPTS = 2

# Paper-exact prompt (Appendix) extended for rich structured output
FINALIZER_PROMPT = """You are an expert data analyst.
You will answer a factoid question by loading and referencing the files listed below.
You also have a reference code and its execution result.
Your task is to make solution code to print out the answer following the given guidelines.

# Given data:
{summaries}

# Reference code
```python
{code}
```

# Execution result of reference code
{result}

# Question
{question}

# Guidelines
{guidelines}

# Output format
Your code MUST print a single JSON object with this exact structure:
{{
  "summary": "2-3 sentence narrative answer to the question",
  "key_findings": [
    "Finding 1 — specific quantitative insight from the data",
    "Finding 2 — specific quantitative insight from the data",
    "Finding 3 — specific quantitative insight from the data"
  ],
  "columns": ["col1", "col2", "col3"],
  "rows": [["val1", "val2", "val3"], ...],
  "chart": {{
    "type": "bar",
    "title": "descriptive chart title",
    "x_key": "name_of_x_column_in_data",
    "x_label": "X axis label",
    "y_key": "name_of_y_column_in_data",
    "y_label": "Y axis label",
    "data": [{{"<x_key>": "entity name", "<y_key>": numeric_value}}, ...]
  }},
  "raw": "the full plain text answer"
}}

Chart type rules:
- Use "bar" when comparing discrete entities (rankings, top-N lists, category totals)
- Use "line" when showing trends over time (dates, periods, sequential steps)
- Use "pie" when showing proportions of a whole (only if 2-6 categories)
- The chart "data" array uses the ACTUAL x_key and y_key strings as keys
- Only include chart if there is meaningful quantitative data to visualize; otherwise set "chart": null
- key_findings must be 2-5 specific, quantified statements from the data (e.g. "National Bank leads with 312 SARs, 32% above the category average")

# Your task
Modify the solution code to print out the answer following the given guidelines.
If the answer can be obtained from the execution result of the reference code, just generate a Python code that prints out the desired answer.
The code should be a single-file Python program that is self-contained and can be executed as-is.
Your response should only contain a single code block.
Do not use try: and except: to prevent error.
If you re-read any CSV file rather than reusing the reference code's already-loaded
result, ALWAYS pass nrows=10000 — no exceptions. The sandbox container is capped at
2GB memory; operations that expand row count (e.g. pd.melt across many columns) on an
unbounded read of a large file will be silently killed with no error output at all.
Never nest an f-string inside another f-string's expression with escaped quotes
(e.g. f"...{{', '.join([f'{{row[\"X\"]}}' for _, row in df.iterrows()])}}...") — this
is invalid Python syntax. Build the inner strings in a separate variable/list first
(e.g. `parts = [f"{{row['X']}}" for _, row in df.iterrows()]`), then interpolate that
variable into the outer string — this applies to the "raw" and "summary" text fields too.
No space after the thousands-separator comma in an f-string format spec — write
f"{{x:,.2f}}", never f"{{x:, .2f}}" (a stray space there is a ValueError at runtime, not
a formatting choice)."""


def finalizer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "finalizer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "finalizer", "Formatting final structured answer...", "running")

    question         = state["query"]
    summaries        = state["data_descriptions"]
    current_script   = state["current_script"]
    execution_result = state["execution_result"]
    guidelines       = state.get("formatting_guidelines", "Print the answer clearly and concisely.")

    summaries_text = format_file_summaries(summaries)

    prompt = FINALIZER_PROMPT.format(
        summaries=summaries_text,
        code=current_script,
        result=execution_result,
        question=question,
        guidelines=guidelines,
    )

    result       = router.complete(agent="finalizer", prompt=prompt, task_id=state["task_id"])
    final_script = strip_code_fences(result["text"].strip())

    stdout, stderr, exit_code = execute_script(final_script, state["task_id"])

    filenames = "\n".join(summaries.keys())
    attempt = 0
    while exit_code != 0 and attempt < MAX_FINALIZER_DEBUG_ATTEMPTS:
        attempt += 1
        logger.error(f"Finalizer script failed (attempt {attempt}): {stderr[:200]}")
        log_event(state["task_id"], "finalizer",
                  f"Finalizer script failed — debug attempt {attempt}/{MAX_FINALIZER_DEBUG_ATTEMPTS}",
                  "error", {"attempt": attempt})

        if "SyntaxError" in stderr or "IndentationError" in stderr:
            # A SyntaxError here almost always means the previous generation was cut
            # off mid-token (e.g. a string literal left unterminated), not a logic bug
            # to patch — asking the model to "fix" an already-incomplete fragment tends
            # to just reproduce the same truncation. A fresh attempt from the original,
            # complete prompt is far more likely to come back as valid, complete code.
            fix_result = router.complete(agent="finalizer", prompt=prompt, task_id=state["task_id"])
        else:
            debug_prompt = DEBUGGER_PROMPT.format(filenames=filenames, code=final_script, bug=stderr)
            fix_result   = router.complete(agent="debugger", prompt=debug_prompt, task_id=state["task_id"])
        final_script = strip_code_fences(fix_result["text"].strip())

        stdout, stderr, exit_code = execute_script(final_script, state["task_id"])

    final_output = stdout if exit_code == 0 else f"Execution failed: {summarize_script_failure(stderr)}"

    # Injected server-side, not trusted to the LLM — same reasoning as writer.py's
    # sources list: the model has no reason to know or report its own retry count or
    # which files were actually profiled for this task. The Insight dashboard's
    # "Analysis Rounds/Tokens/Cost" stat strip was showing a client-side guess
    # (`plan.length * 2500` tokens) because no real signal reached the frontend at all;
    # this is that real signal, riding in the same JSON blob the frontend already parses
    # rather than requiring a new API contract.
    if exit_code == 0:
        try:
            parsed = json.loads(final_output.strip())
            if isinstance(parsed, dict):
                validate_and_log(FinalizerOutput, parsed, task_id=state["task_id"], agent="finalizer")
                parsed["debug_attempts"] = attempt
                parsed["files_used"] = list(summaries.keys())
                final_output = json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            pass  # non-JSON finalizer output — nothing to attach provenance to

    if exit_code == 0:
        logger.info(f"exit={exit_code}")
    else:
        logger.error(f"exit={exit_code}: {stderr[:200]}")
    log_event(state["task_id"], "finalizer",
              "Analysis complete ✓" if exit_code == 0 else f"Finalizer script failed: {summarize_script_failure(stderr)}",
              "success" if exit_code == 0 else "error")

    return {
        "final_result": final_output,
        "status":       "completed" if exit_code == 0 else "failed"
    }
