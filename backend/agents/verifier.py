from agents.state import TaskState, current_objective
from agents.domain_knowledge import retrieve_grounded_knowledge
from agents.logger import log_event
from agents.prompt_store import get_prompt
from llm_router import LLMRouter
from db import supabase
import logging

router = LLMRouter()
logger = logging.getLogger(__name__)

VERIFIER_PROMPT = """You are an expert data analyst.
Your task is to check whether the current plan and its code implementation is enough to answer the question.

# Question
{question}

# Given data:
{summaries}
{domain_knowledge}
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
Verify whether the execution result contains enough information to answer the question.
Bias strongly toward 'Yes' — if the result contains any relevant data, numbers, or table rows
that directly address the question, answer 'Yes'. Only answer 'No' if the result is completely
empty, threw an error, or is entirely unrelated to the question.
Exception to that bias: if "# Domain knowledge" above documents specific value-coding for a
column the code uses (e.g. a flag coded 1/2 rather than 0/1), and the code's arithmetic
treats that column as if it already had the documented "clean" meaning without converting
it first (e.g. summing raw codes as a count, or comparing a raw code to a threshold meant
for a recoded value), answer 'No' — a plausible-looking number computed on a
miscoded/un-recoded column is worse than an empty result, because nothing downstream will
catch that it's silently wrong.
Your response must be exactly one of 'Yes' or 'No'.
Your answer (Yes/No):"""


def verifier(state: TaskState) -> dict:

    supabase.table("tasks").update({"current_agent": "verifier"}).eq("task_id", state["task_id"]).execute()

    question         = current_objective(state)
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

    # Grounded on the step + actual code (not just the question) — the code is what
    # names the exact columns being manipulated, which is what a verifier needs to catch
    # a miscoded/un-recoded column being used. See domain_knowledge.py.
    domain_knowledge = retrieve_grounded_knowledge(f"{current_step}\n{current_script}", state)

    prompt = get_prompt("verifier", VERIFIER_PROMPT).format(
        question=question,
        summaries=summaries_text,
        domain_knowledge=domain_knowledge,
        plan=plan_text,
        current_step=current_step,
        code=current_script,
        result=execution_result
    )

    result  = router.complete(agent="verifier", prompt=prompt, task_id=state["task_id"])
    answer  = result["text"].strip().lower()
    verdict = "sufficient" if "yes" in answer else "insufficient"

    logger.info(f"Verdict: {verdict}")

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "verifier",
              f"{label}Result verified — {'sufficient ✓' if verdict == 'sufficient' else 'needs more work'}",
              "success" if verdict == "sufficient" else "info",
              {"verdict": verdict, "round": state.get("current_round", 0)})

    return {"verifier_verdict": verdict}