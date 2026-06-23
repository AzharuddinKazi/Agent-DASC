from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
import os

router = LLMRouter()

VERIFIER_PROMPT = """You are an expert data analyst.
Your task is to check whether the current plan and its code implementation is enough to answer the question.

# Question
{question}

# Given data:
{summaries}

# Plan
{plan}

# Current step
{current_step}

# Code
[python]
{code}
[/python]

# Execution result of code
{result}

# Your task
Verify whether the current plan and its code implementation is enough to answer the question.
Your response should be one of 'Yes' or 'No'.
If it is enough to answer the question, please answer 'Yes'.
Otherwise, please answer 'No'.
Your answer (Yes/No):"""


def verifier(state: TaskState) -> dict:

    # supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    supabase.table("tasks").update({"current_agent": "verifier"}).eq("task_id", state["task_id"]).execute()

    question         = state["query"]
    summaries        = state["data_descriptions"]
    cumulative_plan  = state["cumulative_plan"]
    current_script   = state["current_script"]
    execution_result = state["execution_result"]

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    plan_text = "\n".join(
        f"Step {i+1}: {step}"
        for i, step in enumerate(cumulative_plan)
    )

    current_step = cumulative_plan[-1] if cumulative_plan else ""

    prompt = VERIFIER_PROMPT.format(
        question=question,
        summaries=summaries_text,
        plan=plan_text,
        current_step=current_step,
        code=current_script,
        result=execution_result
    )

    result  = router.complete(agent="verifier", prompt=prompt)
    answer  = result["text"].strip().lower()
    verdict = "sufficient" if "yes" in answer else "insufficient"

    print(f"[Verifier] Verdict: {verdict}")

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "verifier",
              f"{label}Result verified — {'sufficient ✓' if verdict == 'sufficient' else 'needs more work'}",
              "success" if verdict == "sufficient" else "info",
              {"verdict": verdict, "round": state.get("current_round", 0)})

    return {"verifier_verdict": verdict}