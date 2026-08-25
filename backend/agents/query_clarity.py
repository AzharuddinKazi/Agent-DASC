"""Pre-analysis clarifying questions — runs before the pipeline starts, not as a graph
node. `query_clarity` was already reserved as a "low" tier in llm_router.py ("runs
frequently, simplicity matters") but never implemented; this fills that gap.

Kept deliberately cheap and decoupled from the Analyzer: it reads whatever file
descriptions are already cached in `file_descriptions` (a plain SELECT, no Docker sandbox
spin-up) rather than forcing a full data-profiling pass just to ask a question — the
popup would otherwise block on the same expensive per-file analysis the pipeline does
anyway once the task actually starts. If nothing is cached yet, the model still has the
query text and domain pack context to work with.
"""

import json
import logging
import re

from agents.prompt_store import get_prompt
from db import supabase
from domain_pack import get_active_pack_config
from llm_router import LLMRouter

router = LLMRouter()
logger = logging.getLogger(__name__)

MAX_QUESTIONS = 4
MAX_OPTIONS_PER_QUESTION = 4

QUERY_CLARITY_PROMPT = """You are a senior data analyst about to start an investigation. Before
writing any code, decide whether the research query below is ambiguous in a way that would
materially change what you'd actually go build — not just phrasing preference.

# Research query
{question}

# Analysis mode
{task_type_label}
{domain_section}
# Available data (file names and columns, if already profiled)
{summaries}

# Your task
Ask 0-{max_questions} clarifying questions ONLY if answering them would change which data,
timeframe, entities, or metrics the analysis actually covers — e.g. the query says "top
performers" but the data has multiple plausible ranking metrics, or references a time period
that could mean several different date ranges, or is scoped ambiguously between two available
datasets. Do NOT ask about presentation/formatting choices, and do NOT ask a question whose
answer wouldn't change the actual analysis. If the query is already unambiguous given the
available data, return an empty list — most queries should not need clarification.

Each question must have {max_options} or fewer short, mutually exclusive, concrete answer
options (the user can also type a custom answer, so don't try to enumerate every possibility —
just the most likely ones).

Return ONLY a valid JSON array, no markdown fences, no preamble:
[{{"question": "The question, phrased for the person who wrote the query",
   "header": "Two-word label",
   "options": [{{"label": "Short option text", "description": "One clause of context on what picking this means"}}]}}]"""


def _domain_section(domain_pack_id: str | None) -> str:
    if not domain_pack_id:
        return ""
    try:
        config = get_active_pack_config(domain_pack_id)
    except Exception:
        return ""
    persona = config.get("report_persona") or ""
    if not persona:
        return ""
    return f"\n# Domain context\n{persona}\n"


def _cached_summaries_text() -> str:
    """Best-effort, cache-only — never triggers a fresh Analyzer run. A quiet fallback
    to "no data profiled yet" is correct here, not a bug to fix: the model can still ask
    sensible scoping questions off the query text alone."""
    try:
        rows = supabase.table("file_descriptions").select("filename, description").execute().data
    except Exception:
        rows = []
    if not rows:
        return "(No data has been profiled yet — reason from the query text alone.)"
    parts = []
    for row in rows:
        desc = row["description"] or ""
        # First ~15 lines is enough to see column names without bloating the prompt with
        # every cached file's full row-sample/statistics dump.
        head = "\n".join(desc.splitlines()[:15])
        parts.append(f"File: {row['filename']}\n{head}")
    return "\n\n".join(parts)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-z]*\n?", "", stripped).rstrip("`").strip()
    return stripped


def _json_parse_failed(text: str) -> bool:
    """True when the model produced something other than a clean JSON array — e.g. the
    observed failure mode where a smaller model wraps each question in its own [...]
    instead of one flat array ("[{...}], {...}, {...}()]"). An empty array ("[]", the
    model correctly deciding no clarification is needed) is NOT a failure — only retry
    when the model was actually trying to say something and got the syntax wrong.
    """
    stripped = _strip_fences(text)
    if not stripped:
        return False
    try:
        parsed = json.loads(stripped)
    except Exception:
        return True
    return not isinstance(parsed, list)


def _parse_questions(text: str) -> list[dict]:
    stripped = _strip_fences(text)
    try:
        parsed = json.loads(stripped)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []

    questions = []
    for entry in parsed[:MAX_QUESTIONS]:
        if not isinstance(entry, dict) or not entry.get("question"):
            continue
        options = [
            {"label": opt.get("label", ""), "description": opt.get("description", "")}
            for opt in (entry.get("options") or [])
            if isinstance(opt, dict) and opt.get("label")
        ][:MAX_OPTIONS_PER_QUESTION]
        if len(options) < 2:
            continue  # a "clarifying question" with 0-1 concrete options isn't one
        questions.append({
            "question": entry["question"],
            "header": entry.get("header", "Scope")[:20],
            "options": options,
        })
    return questions


def generate_clarifying_questions(query: str, task_type: str = "qa", domain_pack_id: str | None = None) -> list[dict]:
    task_type_label = "Investigative report (multiple hypothesis-driven sub-analyses)" if task_type == "report" \
        else "Direct Q&A (single focused answer)"

    prompt = get_prompt("query_clarity", QUERY_CLARITY_PROMPT).format(
        question=query,
        task_type_label=task_type_label,
        domain_section=_domain_section(domain_pack_id),
        summaries=_cached_summaries_text(),
        max_questions=MAX_QUESTIONS,
        max_options=MAX_OPTIONS_PER_QUESTION,
    )

    try:
        result = router.complete(agent="query_clarity", prompt=prompt)
    except Exception:
        logger.exception("query_clarity LLM call failed — skipping clarification")
        return []

    text = result["text"]
    if _json_parse_failed(text):
        logger.info("query_clarity output was malformed — retrying once")
        try:
            retry_result = router.complete(agent="query_clarity", prompt=prompt)
            if not _json_parse_failed(retry_result["text"]):
                text = retry_result["text"]
        except Exception:
            logger.exception("query_clarity retry failed — using first (malformed) attempt")

    questions = _parse_questions(text)
    logger.info(f"Generated {len(questions)} clarifying question(s)")
    return questions
