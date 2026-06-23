from agents.state import TaskState
from agents.executor import execute_script
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()

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
Do not use try: and except: to prevent error."""


def finalizer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "finalizer"}).eq("task_id", state["task_id"]).execute()

    question         = state["query"]
    summaries        = state["data_descriptions"]
    current_script   = state["current_script"]
    execution_result = state["execution_result"]
    guidelines       = state.get("formatting_guidelines", "Print the answer clearly and concisely.")

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = FINALIZER_PROMPT.format(
        summaries=summaries_text,
        code=current_script,
        result=execution_result,
        question=question,
        guidelines=guidelines,
    )

    result       = router.complete(agent="finalizer", prompt=prompt)
    final_script = result["text"].strip()

    if final_script.startswith("```"):
        lines        = final_script.split("\n")
        final_script = "\n".join(lines[1:-1])

    stdout, stderr, exit_code = execute_script(final_script)
    final_output = stdout if exit_code == 0 else f"Execution failed:\n{stderr}"
    print(f"[Finalizer] exit={exit_code}")

    return {
        "final_result": final_output,
        "status":       "completed"
    }
