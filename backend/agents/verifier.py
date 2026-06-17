from agents.state import TaskState
from llm_router import LLMRouter

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

    return {"verifier_verdict": verdict}