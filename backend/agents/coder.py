from db import supabase
from agents.logger import log_event
import logging
from agents.state import TaskState
from agents.code_fences import strip_code_fences
from agents.domain_knowledge import retrieve_grounded_knowledge
from llm_router import LLMRouter

router = LLMRouter()
logger = logging.getLogger(__name__)

CODER_INIT = """# Given data:
{summaries}
{domain_knowledge}
# Plan
{plan}

# Rules
- All data files are located at /workspace/data/ — always use full paths
- Example: pd.read_csv('/workspace/data/filename.csv')
- Never use relative paths like 'filename.csv' or './filename.csv'
- For CSV files: default separator is comma. Only try others if comma fails
- Never use shell commands (!head, !cat, etc.) — pure Python only
- Always print results to stdout so they can be captured
- Read the full file — no row limit — unless it's larger than a few hundred MB, in
  which case pass nrows=100000 to stay comfortably within the sandbox's memory
- Never nest an f-string inside another f-string's expression with escaped quotes
  (e.g. f"...{{', '.join([f'{{row[\"X\"]}}' for _, row in df.iterrows()])}}...") — this
  is invalid Python syntax. Build the inner strings in a separate variable/list first
  (e.g. `parts = [f"{{row['X']}}" for _, row in df.iterrows()]`), then interpolate that
  variable into the outer string.

# Your task
Implement the plan with the given data.
Your response should be a single Python code block.
There should be no additional headings or text in your response."""

CODER_NEXT = """You are an expert data analyst.
Your task is to implement the next plan with the given data.

# Given data:
{summaries}
{domain_knowledge}
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
- Read the full file — no row limit — unless it's larger than a few hundred MB, in
  which case pass nrows=100000 to stay comfortably within the sandbox's memory
- Never nest an f-string inside another f-string's expression with escaped quotes
  (e.g. f"...{{', '.join([f'{{row[\"X\"]}}' for _, row in df.iterrows()])}}...") — this
  is invalid Python syntax. Build the inner strings in a separate variable/list first
  (e.g. `parts = [f"{{row['X']}}" for _, row in df.iterrows()]`), then interpolate that
  variable into the outer string.

# Your task
Implement the current plan based on the base code.
Build on top of the base code — do not rewrite from scratch.
Your response should be a single Python code block.
There should be no additional headings or text in your response."""


def coder(state: TaskState) -> dict:

    supabase.table("tasks").update({"current_agent": "coder"}).eq("task_id", state["task_id"]).execute()

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "coder",
              f"{label}Writing Python script · Round {state['current_round']}",
              "running",
              {"round": state["current_round"],
               **({"sub_q_idx": current_sub_idx + 1, "sub_q_total": len(sub_questions)} if sub_questions else {})})

    summaries = state["data_descriptions"]
    cumulative_plan = state["cumulative_plan"]
    prior_script = state.get("current_script", "")

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    plan_text = "\n".join(
        f"Step {i+1}: {step}"
        for i, step in enumerate(cumulative_plan)
    )

    # Retrieval is grounded on the step actually being implemented (most specific about
    # which columns are touched) rather than the whole plan — see domain_knowledge.py.
    current_plan = cumulative_plan[-1] if cumulative_plan else plan_text
    domain_knowledge = retrieve_grounded_knowledge(current_plan, state)

    if not prior_script:
        prompt = CODER_INIT.format(
            summaries=summaries_text,
            plan=plan_text,
            domain_knowledge=domain_knowledge
        )
    else:
        prompt = CODER_NEXT.format(
            summaries=summaries_text,
            base_code=prior_script,
            plan=plan_text,
            current_plan=current_plan,
            domain_knowledge=domain_knowledge
        )

    result = router.complete(agent="coder", prompt=prompt, task_id=state["task_id"])
    script = strip_code_fences(result["text"].strip())

    logger.info(f"Script generated ({result['output_tokens']} tokens)")

    return {"current_script": script}