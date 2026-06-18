from agents.state import TaskState
from llm_router import LLMRouter

router = LLMRouter()

CODER_INIT = """# Given data:
{summaries}

# Plan
{plan}

# Rules
- All data files are located at /workspace/data/ — always use full paths
- Example: pd.read_csv('/workspace/data/filename.csv')
- Never use relative paths like 'filename.csv' or './filename.csv'
- For CSV files: default separator is comma. Only try others if comma fails
- Never use shell commands (!head, !cat, etc.) — pure Python only
- Always print results to stdout so they can be captured
- ALWAYS use nrows=10000 when loading any CSV file — no exceptions

# Your task
Implement the plan with the given data.
Your response should be a single Python code block.
There should be no additional headings or text in your response."""

CODER_NEXT = """You are an expert data analyst.
Your task is to implement the next plan with the given data.

# Given data:
{summaries}

# Base code
```python
{base_code}
```

# Previous plans
{plan}

# Current plan to implement
{current_plan}

# Rules
- All data files are located at /workspace/data/ — always use full paths
- Example: pd.read_csv('/workspace/data/filename.csv')
- Never use relative paths like 'filename.csv' or './filename.csv'
- For CSV files: default separator is comma. Only try others if comma fails
- Never use shell commands — pure Python only
- Always print results to stdout so they can be captured
- ALWAYS use nrows=10000 when loading any CSV file — no exceptions

# Your task
Implement the current plan based on the base code.
Build on top of the base code — do not rewrite from scratch.
Your response should be a single Python code block.
There should be no additional headings or text in your response."""


def coder(state: TaskState) -> dict:
    summaries = state["data_descriptions"]
    cumulative_plan = state["cumulative_plan"]
    prior_script = state.get("current_script", "")
    current_round = state["current_round"]

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    plan_text = "\n".join(
        f"Step {i+1}: {step}"
        for i, step in enumerate(cumulative_plan)
    )

    if not prior_script:
        prompt = CODER_INIT.format(
            summaries=summaries_text,
            plan=plan_text
        )
    else:
        current_plan = cumulative_plan[-1] if cumulative_plan else ""
        prompt = CODER_NEXT.format(
            summaries=summaries_text,
            base_code=prior_script,
            plan=plan_text,
            current_plan=current_plan
        )

    result = router.complete(agent="coder", prompt=prompt)
    script = result["text"].strip()

    if script.startswith("```"):
        lines = script.split("\n")
        script = "\n".join(lines[1:-1])

    print(f"[Coder] Script generated ({result['output_tokens']} tokens)")

    return {"current_script": script}