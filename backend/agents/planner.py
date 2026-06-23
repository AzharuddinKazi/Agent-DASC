import os

from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
router = LLMRouter()

PLANNER_INIT = """You are an expert data analyst.
    In order to answer factoid questions based on the given data, you have to first plan effectively.

    # Question
    {question}

    # Given data:
    {summaries}

    # Your task
    Suggest your very first step to answer the question above.
    Your first step does not need to be sufficient to answer the question.
    Just propose a very simple initial step, which can act as a good starting point.
    Your response should only contain an initial step."""

PLANNER_NEXT = """You are an expert data analyst.
    In order to answer factoid questions based on the given data, you have to first plan effectively.
    Your task is to suggest the next plan to answer the question.

    # Question
    {question}

    # Given data:
    {summaries}

    # Current plans
    {plan}

    # Current step
    {current_step}

    # Obtained results from the current plans:
    {result}

    # Your task
    Suggest your next step to answer the question above.
    Your next step does not need to be sufficient to answer the question, but if it
    requires only a final simple last step you may suggest it.
    Just propose a very simple next step, which can act as a good intermediate point.
    Your response should only contain a next step without any explanation."""


def planner(state: TaskState) -> dict:
    
    # supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    supabase.table("tasks").update({"current_agent": f"planner_round_{state['current_round']}"}).eq("task_id", state["task_id"]).execute()

    question = state["query"]
    summaries = state["data_descriptions"]
    cumulative_plan = state["cumulative_plan"]
    current_round = state["current_round"]
    last_result = state.get("execution_result", "")

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    plan_text = "\n".join(
        f"Step {i+1}: {step}"
        for i, step in enumerate(cumulative_plan)
    )

    if current_round == 0:
        prompt = PLANNER_INIT.format(
            question=question,
            summaries=summaries_text
        )
    else:
        current_step = cumulative_plan[-1] if cumulative_plan else ""
        prompt = PLANNER_NEXT.format(
            question=question,
            summaries=summaries_text,
            plan=plan_text,
            current_step=current_step,
            result=last_result if last_result else "No result yet."
        )

    result = router.complete(agent="planner", prompt=prompt)
    new_step = result["text"].strip()

    print(f"[Planner] Round {current_round + 1}: {new_step}")

    updated_plan = cumulative_plan + [new_step]
    supabase.table("tasks").update({
        "cumulative_plan": updated_plan
    }).eq("task_id", state["task_id"]).execute()

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    sub_ctx = {}
    if sub_questions:
        sub_ctx = {
            "sub_q_idx":   current_sub_idx + 1,
            "sub_q_total": len(sub_questions),
            "sub_q_text":  sub_questions[current_sub_idx] if current_sub_idx < len(sub_questions) else "",
        }

    label = f"Sub-Q {current_sub_idx + 1}/{len(sub_questions)} · " if sub_questions else ""
    log_event(state["task_id"], "planner",
              f"{label}Round {current_round + 1} — {new_step}",
              "running", {"round": current_round + 1, **sub_ctx})

    return {
        "cumulative_plan": updated_plan,
        "current_round":   current_round + 1,
        "status":          "running",
    }
