import logging
from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
from domain_pack import get_active_pack_config

router = LLMRouter()
logger = logging.getLogger(__name__)

QUESTION_GENERATOR_PROMPT = """You are a senior research analyst.
Your task is to decompose a broad research query into a set of non-overlapping sub-questions,
each covering a DISTINCT analytical dimension. Together they must give a complete picture.

# Research Query
{question}

# Available Data
{summaries}
{dimensions_section}
For each sub-question:
- Be specific and quantitative ("Top 5 entities by revenue growth" not "Tell me about revenue")
- Confirm it is answerable from the available columns before including it
- Each must address a DIFFERENT dimension — no duplicates

Return ONLY a valid JSON array of strings. No preamble, no explanation, no markdown fences.
["Sub-question 1?", "Sub-question 2?", ...]"""


def _dimensions_section() -> str:
    """Built per-call from the active domain pack's config (switchable at runtime — see
    domain_pack.py). When configured, nudges toward those topics; otherwise — the
    default — lets the model choose its own dimensions, covering whatever angles are
    actually relevant to the query and data at hand.
    """
    dimensions = get_active_pack_config()["subquestion_dimensions"]
    if dimensions:
        dims = "\n".join(f"{i}. {d}" for i, d in enumerate(dimensions, 1))
        return f"""
# Mandatory coverage rules
You MUST produce exactly one sub-question per dimension listed below (where the data supports it).
Do NOT produce two sub-questions on the same dimension — merge them into one.

Dimensions to cover (pick the most relevant 5-6 given the query and available data):
{dims}
"""
    return """
# Your task
Identify the distinct analytical dimensions most relevant to answering this query well,
and generate as many sub-questions as needed to cover them — each sub-question must
address a different dimension, with no duplicates.
"""


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
        dimensions_section=_dimensions_section(),
    )

    result = router.complete(agent="question_generator", prompt=prompt)
    text   = result["text"].strip()

    import json, re
    try:
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
        sub_questions = json.loads(text)
        if not isinstance(sub_questions, list):
            sub_questions = [str(sub_questions)]
    except Exception:
        sub_questions = [ln.lstrip("0123456789.-) ").strip() for ln in text.splitlines() if ln.strip()]

    # Deduplicate while preserving order
    seen, unique = set(), []
    for q in sub_questions:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    sub_questions = unique

    logger.info(f"Generated {len(sub_questions)} sub-questions")
    log_event(state["task_id"], "question_generator",
              f"Generated {len(sub_questions)} sub-questions for the report",
              "success", {"sub_questions": sub_questions})

    return {
        "sub_questions":   sub_questions,
        "current_sub_idx": 0,
        "sub_results":     {},
    }
