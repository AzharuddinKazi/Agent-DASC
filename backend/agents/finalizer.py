import ast
import json
import logging
from agents.state import TaskState
from agents.executor import execute_script
from agents.debugger import DEBUGGER_PROMPT
from agents.code_fences import strip_code_fences
from agents.logger import log_event
from agents.prompt_store import get_prompt
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()
logger = logging.getLogger(__name__)


def _repair_python_repr(text: str):
    """The prompt tells the generated script to `print()` JSON, but a model sometimes
    does the more natural-feeling Python thing instead — `print(result_dict)` — which
    comes out as a Python repr (single-quoted keys, True/False/None) instead of JSON
    (double-quoted, true/false/null). json.loads rejects that outright. ast.literal_eval
    parses exactly the literal syntax Python's own repr produces (dict/list/str/int/
    float/bool/None/tuple — never arbitrary code, unlike eval), so round-tripping through
    it recovers the same structure json.dumps then serializes correctly. Mirrors
    writer.py's _strip_invalid_escapes — same shape of problem (near-miss LLM "JSON"),
    different specific mistake."""
    return ast.literal_eval(text)


def _extract_trailing_object(text: str) -> str:
    """The prompt says "print a single JSON object", but a model sometimes leaves in
    its exploratory prints too (df.head(), intermediate column listings, etc.) with the
    actual answer object only as the last line — neither json.loads nor
    _repair_python_repr can parse that mix as one literal. Recover it by taking
    everything from the LAST '{' onward: the model's own object is always the final
    print, so the last '{' in the whole output starts it (an earlier '{' would only
    belong to debug output that comes before it, never after)."""
    idx = text.rfind("{")
    if idx == -1:
        raise ValueError("no '{' found in output")
    return text[idx:]

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
result, read the full file — no row limit — unless it's larger than a few hundred MB,
in which case pass nrows=100000 to stay comfortably within the sandbox's memory.
Note that operations that expand row count (e.g. pd.melt across many columns) can
still exceed the sandbox's memory cap even on a moderately-sized file, and will be
silently killed with no error output at all — prefer aggregating before expanding
where possible.
Never nest an f-string inside another f-string's expression with escaped quotes
(e.g. f"...{{', '.join([f'{{row[\"X\"]}}' for _, row in df.iterrows()])}}...") — this
is invalid Python syntax. Build the inner strings in a separate variable/list first
(e.g. `parts = [f"{{row['X']}}" for _, row in df.iterrows()]`), then interpolate that
variable into the outer string — this applies to the "raw" and "summary" text fields too."""


def finalizer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "finalizer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "finalizer", "Formatting final structured answer...", "running")

    question         = state["query"]
    summaries        = state["data_descriptions"]
    current_script   = state["current_script"]
    execution_result = state["execution_result"]
    guidelines       = state.get("formatting_guidelines", "Print the answer clearly and concisely.")

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = get_prompt("finalizer", FINALIZER_PROMPT).format(
        summaries=summaries_text,
        code=current_script,
        result=execution_result,
        question=question,
        guidelines=guidelines,
    )

    result       = router.complete(agent="finalizer", prompt=prompt, task_id=state["task_id"])
    final_script = strip_code_fences(result["text"].strip())

    stdout, stderr, exit_code = execute_script(final_script, state["task_id"])

    # A script that exits 0 but prints nothing is just as unusable as one that errors —
    # observed live 2026-08-23 (see TASKS.md): exit_code 0, empty stdout, silently
    # reported as a "completed" task with an empty final_result and no indication
    # anything went wrong. Treated as a failure for retry purposes below, same as a
    # nonzero exit — but never reported to the user as "Execution failed" (there was no
    # execution error), see final_output's own empty-after-retries case further down.
    def _blank(out: str, code: int) -> bool:
        return code == 0 and not out.strip()

    filenames = "\n".join(summaries.keys())
    attempt = 0
    while (exit_code != 0 or _blank(stdout, exit_code)) and attempt < MAX_FINALIZER_DEBUG_ATTEMPTS:
        attempt += 1
        blank = _blank(stdout, exit_code)
        bug_description = stderr if not blank else (
            "The script ran without any error, but printed nothing to stdout. It must "
            "end by printing the final answer — add the missing print() call."
        )
        logger.error(f"Finalizer script failed (attempt {attempt}): "
                     f"{'no output' if blank else stderr[:200]}")
        log_event(state["task_id"], "finalizer",
                  f"Finalizer script failed — debug attempt {attempt}/{MAX_FINALIZER_DEBUG_ATTEMPTS}",
                  "error", {"attempt": attempt})

        if not blank and ("SyntaxError" in stderr or "IndentationError" in stderr):
            # A SyntaxError here almost always means the previous generation was cut
            # off mid-token (e.g. a string literal left unterminated), not a logic bug
            # to patch — asking the model to "fix" an already-incomplete fragment tends
            # to just reproduce the same truncation. A fresh attempt from the original,
            # complete prompt is far more likely to come back as valid, complete code.
            fix_result = router.complete(agent="finalizer", prompt=prompt, task_id=state["task_id"])
        else:
            debug_prompt = get_prompt("debugger", DEBUGGER_PROMPT).format(filenames=filenames, code=final_script, bug=bug_description)
            fix_result   = router.complete(agent="debugger", prompt=debug_prompt, task_id=state["task_id"])
        final_script = strip_code_fences(fix_result["text"].strip())

        stdout, stderr, exit_code = execute_script(final_script, state["task_id"])

    if exit_code != 0:
        final_output = f"Execution failed:\n{stderr}"
    elif not stdout.strip():
        # Ran clean but produced nothing, even after exhausting retries — report this
        # honestly as a failure rather than "completed" with an empty result the
        # frontend would render as a blank/broken answer with no explanation. stderr
        # is empty in this case (there was no execution error), so give the log/error
        # message below something more useful than a blank string to display.
        stderr = "the script ran without error but produced no output"
        final_output = f"Execution failed:\n{stderr}"
        exit_code = 1
    else:
        final_output = stdout

    # Injected server-side, not trusted to the LLM — same reasoning as writer.py's
    # sources list: the model has no reason to know or report its own retry count or
    # which files were actually profiled for this task. The Insight dashboard's
    # "Analysis Rounds/Tokens/Cost" stat strip was showing a client-side guess
    # (`plan.length * 2500` tokens) because no real signal reached the frontend at all;
    # this is that real signal, riding in the same JSON blob the frontend already parses
    # rather than requiring a new API contract.
    if exit_code == 0:
        stripped = final_output.strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            try:
                parsed = _repair_python_repr(stripped)
                logger.info("Finalizer output was a Python repr, not JSON — repaired and parsed")
            except (ValueError, SyntaxError, TypeError):
                # Last resort: the model left earlier prints (df.head(), column dumps,
                # ...) before its actual answer object — try just the trailing object,
                # via both parsers again since it could be either JSON or a Python repr.
                try:
                    trailing = _extract_trailing_object(stripped)
                    try:
                        parsed = json.loads(trailing)
                    except json.JSONDecodeError:
                        parsed = _repair_python_repr(trailing)
                    logger.info("Finalizer output had extra prints before its answer object — "
                                "extracted and parsed the trailing object")
                except (ValueError, SyntaxError, TypeError):
                    parsed = None
                    logger.warning("Finalizer output wasn't valid JSON or a Python literal — shipping it unparsed")

        if isinstance(parsed, dict):
            parsed["debug_attempts"] = attempt
            parsed["files_used"] = list(summaries.keys())
            final_output = json.dumps(parsed)

    if exit_code == 0:
        logger.info(f"exit={exit_code}")
    else:
        logger.error(f"exit={exit_code}: {stderr[:200]}")
    log_event(state["task_id"], "finalizer",
              "Analysis complete ✓" if exit_code == 0 else f"Finalizer script failed: {stderr[:120]}",
              "success" if exit_code == 0 else "error")

    return {
        "final_result": final_output,
        "status":       "completed" if exit_code == 0 else "failed"
    }
