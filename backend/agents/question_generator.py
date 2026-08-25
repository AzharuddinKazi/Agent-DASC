import logging
from agents.state import TaskState
from agents.logger import log_event
from agents.prompt_store import get_prompt
from llm_router import LLMRouter
from db import supabase
from domain_pack import get_active_pack_config

router = LLMRouter()
logger = logging.getLogger(__name__)

QUESTION_GENERATOR_PROMPT = """You are a senior research analyst planning an investigative report.
Your task is to decompose a broad research query into a SEQUENCE of testable hypotheses that
together tell a cohesive analytical story — not an independent checklist of topics.

# Research Query
{question}

# Available Data
{summaries}
{dimensions_section}
# How to do this
1. Identify the 4-7 most important, SPECIFIC, testable hypotheses that — if confirmed or
   refuted — would give a complete, decision-useful answer to the research query.
2. ORDER them as a narrative arc: start broad (establish the overall picture), then narrow
   into the most significant finding, then probe its likely cause/driver, then check for
   secondary/contributing factors. Later hypotheses should read as natural follow-ups to
   what an analyst would want to know after confirming the earlier ones — not a
   randomly-ordered topic list.
3. For each hypothesis, write ONE specific, quantitative analytical question that tests it
   and is answerable from the available columns (e.g. "Fraud rate by channel-emirate
   combination, ranked, with the top combination's deviation from the population average" —
   not "Tell me about fraud by channel").

Return ONLY a valid JSON array of objects, ordered as the narrative sequence. No preamble,
no explanation, no markdown fences.
[{{"hypothesis": "Specific, falsifiable claim", "question": "The analytical question that tests it"}}, ...]"""


def _dimensions_section(domain_pack_id: str | None) -> str:
    """Built per-call from a domain pack's config (switchable at runtime — see
    domain_pack.py). domain_pack_id pins a specific pack for this task; None uses
    whichever pack is globally active. When configured, nudges toward those topics;
    otherwise — the default — lets the model choose its own dimensions, covering
    whatever angles are actually relevant to the query and data at hand.
    """
    dimensions = get_active_pack_config(domain_pack_id)["subquestion_dimensions"]
    if dimensions:
        dims = "\n".join(f"{i}. {d}" for i, d in enumerate(dimensions, 1))
        return f"""
# Mandatory coverage rules
Each dimension listed below must be covered by at least one hypothesis (where the data
supports it). Do NOT produce two hypotheses on the same dimension — merge them into one.

Dimensions to cover (pick the most relevant 5-6 given the query and available data):
{dims}
"""
    return """
# Your task
Identify the distinct analytical dimensions most relevant to answering this query well,
and generate as many hypotheses as needed to cover them — each hypothesis must address a
different dimension, with no duplicates.
"""


def _parse_hypotheses(text: str) -> list[dict]:
    """Returns a list of {"hypothesis": str, "question": str} dicts, in narrative order.

    Tolerates the model returning a plain string array (ignoring the requested shape) by
    treating each string as a question with no hypothesis — degraded, not broken. The
    non-JSON fallback (line-splitting) produces the same degraded shape.
    """
    import json, re
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-z]*\n?", "", stripped).rstrip("`").strip()

    try:
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            parsed = [parsed]
    except Exception:
        return [
            {"hypothesis": "", "question": ln.lstrip("0123456789.-) ").strip()}
            for ln in text.splitlines() if ln.strip()
        ]

    items = []
    for entry in parsed:
        if isinstance(entry, dict) and entry.get("question"):
            items.append({"hypothesis": entry.get("hypothesis", ""), "question": entry["question"]})
        elif isinstance(entry, str) and entry.strip():
            items.append({"hypothesis": "", "question": entry.strip()})
    return items


def _looks_malformed(items: list[dict]) -> bool:
    """True when parsing "succeeded" but clearly didn't — e.g. the model's JSON array
    got truncated/garbled mid-generation and the line-splitting fallback swallowed the
    whole corrupted blob as a single giant "question" instead of failing loudly. A real
    analytical question is a sentence, not a serialized array — anything this long or
    containing raw JSON syntax is the fallback's failure mode, not a valid result.
    """
    if not items:
        return True
    return any(
        len(item["question"]) > 400 or '"hypothesis"' in item["question"]
        for item in items
    )


def question_generator(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "question_generator"}).eq("task_id", state["task_id"]).execute()

    question  = state["query"]
    summaries = state["data_descriptions"]

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = get_prompt("question_generator", QUESTION_GENERATOR_PROMPT).format(
        question=question,
        summaries=summaries_text,
        dimensions_section=_dimensions_section(state.get("domain_pack_id")),
    )

    result = router.complete(agent="question_generator", prompt=prompt, task_id=state["task_id"])
    items  = _parse_hypotheses(result["text"].strip())

    if _looks_malformed(items):
        log_event(state["task_id"], "question_generator",
                  "Model output was malformed/truncated — retrying once", "info")
        result = router.complete(agent="question_generator", prompt=prompt, task_id=state["task_id"])
        retry_items = _parse_hypotheses(result["text"].strip())
        if not _looks_malformed(retry_items):
            items = retry_items

    # Deduplicate by question text while preserving narrative order
    seen, unique = set(), []
    for item in items:
        if item["question"] not in seen:
            seen.add(item["question"])
            unique.append(item)

    sub_questions = [item["question"] for item in unique]
    hypotheses    = {item["question"]: item["hypothesis"] for item in unique if item["hypothesis"]}

    logger.info(f"Generated {len(sub_questions)} hypothesis-driven sub-questions")
    log_event(state["task_id"], "question_generator",
              f"Generated {len(sub_questions)} sub-questions for the report",
              "success", {"sub_questions": sub_questions, "hypotheses": hypotheses})

    return {
        "sub_questions":       sub_questions,
        "hypotheses":          hypotheses,
        "current_sub_idx":     0,
        "sub_results":         {},
        "sub_question_rounds": {q: 0 for q in sub_questions},
    }
