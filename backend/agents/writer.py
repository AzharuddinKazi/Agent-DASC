import logging
import re
from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
from domain_pack import get_active_pack_config
import json

router = LLMRouter()
logger = logging.getLogger(__name__)

_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _strip_invalid_escapes(text: str) -> str:
    """Report-writing models routinely backslash-escape currency/punctuation out of a
    LaTeX/markdown habit (e.g. "\\$592,300"), which isn't a legal JSON string escape
    (only \\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t, \\uXXXX are) and breaks json.loads on
    every report mentioning a dollar amount. Dropping the stray backslash recovers the
    intended literal character without touching genuinely valid escapes."""
    return _INVALID_ESCAPE.sub("", text)

# Split around the persona and the optional classification line, both of which come from
# the active domain pack's config and can change at runtime — see _build_prompt() below.
_PROMPT_HEAD = """
You have completed {sub_q_count} targeted data analyses. Your job is to synthesise these into a
formal, publication-quality report — NOT a list of data summaries.

# Research Query (the report must answer this)
{question}

# Completed Sub-Analyses
{sub_analyses}

# Report Writing Rules
1. SYNTHESISE, don't list. Each section must weave findings from multiple sub-analyses into a
   coherent narrative. A section is NOT a summary of one sub-question — it is a thematic argument
   supported by data from across the analyses.
2. CITE numbers precisely. Every claim must be backed by a specific figure from the data
   (e.g. "Entity-07 recorded a 8.3% rate, nearly 3× the average of 2.9%").
3. USE formal, professional language. Avoid casual phrasing. Write as if this will be read
   by senior stakeholders making decisions based on it.
4. STRUCTURE thematically. Group related findings under clear themes, not by sub-question.
5. RECOMMEND actions. The conclusions section must end with 3-5 specific, actionable
   recommendations.
6. Identify 2-4 evaluative dimensions most relevant to this query (e.g. for a sales query
   that might be "Revenue Risk" / "Growth Trend"; for an operations query it might be
   "Efficiency" / "Reliability") and use them consistently as the keys in each risk_matrix
   entry's "dimensions" object.
7. CITE your sources. Each numbered analysis above (Analysis 1, Analysis 2, ...) is a
   citable source. Every claim in executive_summary, section bodies, key_stat, and
   conclusions must end with a bracketed citation to the analysis/analyses it draws from,
   e.g. "...a 8.3% rate, nearly 3× the average of 2.9% [2]." or "...across three regions
   [1,4]." Do NOT invent a "sources" or "references" field yourself — citation numbers are
   the only citation mechanism; the reference list is attached separately.
8. Where an analysis states the hypothesis it tested, explicitly say whether that hypothesis
   was CONFIRMED, REFUTED, or NUANCED (partially true, true under specific conditions, etc.)
   — don't just report the number, state what it means for the claim being tested. The
   report as a whole should read as an investigative arc: each section should build on what
   the previous one established, not restate it as a disconnected topic summary.
9. Your entire response must be a single valid JSON string per the format below. Do NOT
   backslash-escape punctuation that isn't a JSON control character — write "$592,300", not
   "\\$592,300"; a backslash is only ever valid before ", \\, /, b, f, n, r, t, or u. Use
   plain ASCII square brackets for citations, e.g. [2] or [1,4] — never full-width or any
   other bracket variant.

# Required Output Format (strict JSON — return ONLY this, no markdown fences)
{{
  "title": "Formal report title","""

_PROMPT_TAIL = """
  "reporting_period": "Based on available data",
  "executive_summary": "4-6 sentences. State the most critical findings directly. Name the standout entities. Quantify the impact. End with the overall assessment.",
  "sections": [
    {{
      "heading": "Thematic section heading (e.g. '1. Revenue Trends and Growth')",
      "body": "3-5 paragraphs of formal narrative. Must include specific entity names/IDs, exact figures, comparisons to benchmarks, and cross-references to other dimensions. Use markdown for emphasis: **bold** for key entities, `code` for metric names.",
      "key_stat": "Single most important number from this section (e.g. 'Average growth rate: 4.2%')"
    }}
  ],
  "risk_matrix": [
    {{
      "entity": "Entity name or ID",
      "dimensions": {{"Dimension Name": "High / Medium / Low", "Another Dimension": "High / Medium / Low"}},
      "overall": "High / Medium / Low",
      "priority_action": "One-line recommended action"
    }}
  ],
  "conclusions": "5-7 sentences summarising overall findings and the urgency of action required.",
  "recommendations": [
    "Specific recommendation 1 addressed to a named entity or the whole population",
    "Specific recommendation 2",
    "Specific recommendation 3"
  ],
  "data_coverage": {{
    "sub_questions_answered": {sub_q_count},
    "total_records_analysed": <integer — sum of row counts from all sub-analyses>,
    "datasets_used": [<list of distinct filenames referenced in the analyses>]
  }}
}}"""


def _writer_prompt_template(domain_pack_id: str | None) -> str:
    """Assembles the Writer's prompt template from a domain pack's config, built
    per-call since the active pack can change at runtime (see domain_pack.py).
    domain_pack_id pins a specific pack for this task; None uses whichever pack is
    globally active. Only asks for a classification field when one is actually
    configured — omitting it from both the instructions and the JSON schema keeps
    unconfigured deployments from getting a fabricated "CONFIDENTIAL"-style label they
    never asked for.
    """
    config = get_active_pack_config(domain_pack_id)
    classification_line = (
        f'\n  "classification": "{config["report_classification"]}",'
        if config["report_classification"] else ""
    )
    return config["report_persona"] + _PROMPT_HEAD + classification_line + _PROMPT_TAIL


def writer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "writer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "writer",
              f"Synthesising report from {len(state.get('sub_results', {}))} sub-analyses...",
              "running", {"sub_q_count": len(state.get("sub_questions", []))})

    question      = state["query"]
    sub_questions = state.get("sub_questions", [])
    sub_results   = state.get("sub_results", {})
    hypotheses    = state.get("hypotheses", {})

    sub_analyses_parts = []
    for i, sq in enumerate(sub_questions):
        sr = sub_results.get(sq, {})
        hypothesis_line = f"\nHypothesis tested: {hypotheses[sq]}" if hypotheses.get(sq) else ""
        part = f"""### Analysis {i+1}: {sq}{hypothesis_line}
Summary: {sr.get('summary', 'No result available')}
Key Findings: {json.dumps(sr.get('key_findings', []), indent=2)}
Columns: {json.dumps(sr.get('columns', []))}
Data rows (first 8): {json.dumps(sr.get('rows', [])[:8])}"""
        sub_analyses_parts.append(part)

    sub_analyses_text = "\n\n".join(sub_analyses_parts)

    prompt = _writer_prompt_template(state.get("domain_pack_id")).format(
        question=question,
        sub_analyses=sub_analyses_text,
        sub_q_count=len(sub_questions),
    )

    result      = router.complete(agent="writer", prompt=prompt, task_id=state["task_id"])
    report_text = result["text"].strip()

    if report_text.startswith("```"):
        report_text = re.sub(r"^```[a-z]*\n?", "", report_text).rstrip("`").strip()

    # The LLM only emits [N] citation markers in the prose — the reference list itself is
    # built here from sub_questions, not trusted to the LLM, so citation numbers are always
    # correct/complete even if the model omits or miscounts them.
    sources = [
        {
            "id": i + 1,
            "question": sq,
            "summary": sub_results.get(sq, {}).get("summary", ""),
            "hypothesis": hypotheses.get(sq, ""),
        }
        for i, sq in enumerate(sub_questions)
    ]
    try:
        parsed = json.loads(report_text)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(_strip_invalid_escapes(report_text))
            logger.info("Writer output had invalid JSON escapes — repaired and parsed")
        except json.JSONDecodeError:
            parsed = None
            logger.warning("Writer output wasn't valid JSON — shipping it unparsed, without a sources list")

    if parsed is not None:
        parsed["sources"] = sources
        report_text = json.dumps(parsed)

    logger.info(f"Report generated ({result['output_tokens']} tokens)")
    log_event(state["task_id"], "writer", "Draft report generated — sending for evaluation", "success")

    return {"draft_report": report_text}
