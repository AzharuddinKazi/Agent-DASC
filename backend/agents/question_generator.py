from agents.state import TaskState
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()

# Decomposes an open-ended query into targeted, answerable sub-questions
QUESTION_GENERATOR_PROMPT = """You are an expert data analyst and research director.
Your task is to decompose a broad, open-ended research query into specific, answerable sub-questions
that together will form a comprehensive analytical report.

# Research Query
{question}

# Available Data
{summaries}

# Your task
Generate 4 to 7 specific sub-questions that, when answered individually using the available data,
will together provide a thorough answer to the research query.

Requirements for each sub-question:
- Must be answerable directly from the available data files
- Must be specific and quantitative where possible (e.g. "What are the top 5 LFIs by SAR volume?" not "Tell me about LFIs")
- Must cover different dimensions of the research query (trends, rankings, comparisons, anomalies)
- Must be a factoid question that produces a table or numeric answer

Return ONLY a JSON array of strings, one sub-question per element. No preamble or explanation.
Example format:
["Sub-question 1?", "Sub-question 2?", "Sub-question 3?"]"""


def question_generator(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "question_generator"}).eq("task_id", state["task_id"]).execute()

    question  = state["query"]
    summaries = state["data_descriptions"]

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = QUESTION_GENERATOR_PROMPT.format(
        question=question,
        summaries=summaries_text,
    )

    result = router.complete(agent="question_generator", prompt=prompt)
    text   = result["text"].strip()

    # Parse JSON array
    import json, re
    try:
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        sub_questions = json.loads(text)
        if not isinstance(sub_questions, list):
            sub_questions = [str(sub_questions)]
    except Exception:
        # Fallback: treat each line as a sub-question
        sub_questions = [ln.lstrip("0123456789.-) ").strip() for ln in text.splitlines() if ln.strip()]

    print(f"[QuestionGenerator] Generated {len(sub_questions)} sub-questions")

    return {
        "sub_questions":    sub_questions,
        "current_sub_idx":  0,
        "sub_results":      {},
    }
