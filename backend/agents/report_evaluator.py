import logging
from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()
logger = logging.getLogger(__name__)

REPORT_EVALUATOR_PROMPT = """You are an expert research quality reviewer.
Your task is to evaluate whether a generated research report sufficiently answers the original research query.

# Original Research Query
{question}

# Hypotheses Investigated (in narrative order)
{hypotheses}

# Generated Report
{report}

# Evaluation criteria
1. Does the executive summary directly answer the research query?
2. Are all major dimensions of the query addressed in the sections?
3. Are findings specific and quantified (not vague)?
4. Does the conclusion include actionable recommendations?
5. Is the report coherent and well-structured?
6. Do the hypotheses build into a cohesive investigative narrative — each finding informing
   the next — rather than reading as disconnected topic summaries?
7. Is each section developed with real depth — explaining the mechanism behind a finding and
   its implications, not just stating a number — or is it thin/superficial, reading like an
   abstract rather than a comprehensive professional report? A section that only takes a
   paragraph or two to make its point has NOT been developed enough.

A report that is well-structured and correct but shallow — covering every theme in only a
sentence or two each — should be marked "insufficient" on criterion 7 alone, with gaps asking
for the underdeveloped themes to be investigated further and expanded with more depth and
supporting detail, not just re-verified.

# Your task
Evaluate the report against the criteria above.
Respond with a JSON object:
{{
  "verdict": "sufficient" or "insufficient",
  "gaps": [{{"question": "Specific follow-up analytical question", "hypothesis": "The claim it would test"}}]
}}

If verdict is "sufficient", gaps should be an empty list.
If verdict is "insufficient", each gap must be a genuine next step in the story — a question
that follows naturally from what's already been established, not an unrelated topic bolted
on to pad coverage.
Return only the JSON object."""


def _normalize_gaps(raw) -> list[dict]:
    """Tolerates the model returning plain gap strings despite the requested shape —
    treated as a question with no hypothesis, same degradation pattern as
    question_generator._parse_hypotheses."""
    gaps = []
    for entry in raw or []:
        if isinstance(entry, dict) and entry.get("question"):
            gaps.append({"question": entry["question"], "hypothesis": entry.get("hypothesis", "")})
        elif isinstance(entry, str) and entry.strip():
            gaps.append({"question": entry.strip(), "hypothesis": ""})
    return gaps


def report_evaluator(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "report_evaluator"}).eq("task_id", state["task_id"]).execute()

    question      = state["query"]
    draft_report  = state.get("draft_report", "")
    sub_questions = state.get("sub_questions", [])
    hypotheses    = state.get("hypotheses", {})

    hypotheses_text = "\n".join(
        f"{i+1}. {hypotheses[sq]}" if hypotheses.get(sq) else f"{i+1}. (no hypothesis recorded) {sq}"
        for i, sq in enumerate(sub_questions)
    ) or "None recorded."

    prompt = REPORT_EVALUATOR_PROMPT.format(
        question=question,
        hypotheses=hypotheses_text,
        report=draft_report,
    )

    result = router.complete(agent="report_evaluator", prompt=prompt, task_id=state["task_id"])
    text   = result["text"].strip()

    import json
    from agents.code_fences import strip_code_fences
    text = strip_code_fences(text)

    try:
        parsed  = json.loads(text)
        verdict = parsed.get("verdict", "sufficient")
        gaps    = _normalize_gaps(parsed.get("gaps", []))
        parse_failed = False
    except Exception:
        logger.warning(f"report_evaluator response wasn't valid JSON — treating conservatively as insufficient: {text[:200]!r}")
        verdict = "insufficient"
        gaps    = []
        parse_failed = True

    logger.info(f"Verdict: {verdict}, gaps: {gaps}")
    gap_text = f" — gaps: {'; '.join(g['question'] for g in gaps[:3])}" if gaps else ""
    if parse_failed:
        message = "Report quality check failed to parse — treating conservatively as insufficient"
        level = "error"
    else:
        message = f"Report quality: {'sufficient ✓' if verdict == 'sufficient' else f'insufficient{gap_text}'}"
        level = "success" if verdict == "sufficient" else "info"
    log_event(state["task_id"], "report_evaluator", message, level,
              {"verdict": verdict, "gaps": gaps, "round": state.get("report_rounds", 0) + 1, "parse_failed": parse_failed})

    return {
        "report_verdict": verdict,
        "report_gaps":    gaps,
        "report_rounds":  state.get("report_rounds", 0) + 1,
    }
