from agents.state import TaskState
from llm_router import LLMRouter

router = LLMRouter()

ROUTER_PROMPT = """You are an expert data analyst.
Since the current plan is insufficient to answer the question, your task is to decide how to refine the plan.

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
If you think one of the steps of the current plans is wrong, answer among the following options: Step 1, Step 2, ..., Step K.
If you think we should perform a new NEXT step, answer as 'Add Step'.
Your response should only be Step 1 ... Step K or Add Step."""


def router_agent(state: TaskState) -> dict:
    question        = state["query"]
    summaries       = state["data_descriptions"]
    cumulative_plan = state["cumulative_plan"]
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

    prompt = ROUTER_PROMPT.format(
        question=question,
        summaries=summaries_text,
        plan=plan_text,
        current_step=current_step,
        result=execution_result
    )

    result   = router.complete(agent="router", prompt=prompt)
    decision = result["text"].strip()

    print(f"[Router] Decision: {decision}")

    if decision.lower().startswith("step"):
        try:
            step_num = int(decision.split()[1])
            return {
                "router_decision": f"backtrack:{step_num}",
                "cumulative_plan": cumulative_plan[:step_num - 1],
            }
        except (IndexError, ValueError):
            return {"router_decision": "add_step"}
    else:
        return {"router_decision": "add_step"}