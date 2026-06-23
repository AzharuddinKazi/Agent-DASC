from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()

REPORT_EVALUATOR_PROMPT = """You are an expert research quality reviewer.
Your task is to evaluate whether a generated research report sufficiently answers the original research query.

# Original Research Query
{question}

# Generated Report
{report}

# Evaluation criteria
1. Does the executive summary directly answer the research query?
2. Are all major dimensions of the query addressed in the sections?
3. Are findings specific and quantified (not vague)?
4. Does the conclusion include actionable recommendations?
5. Is the report coherent and well-structured?

# Your task
Evaluate the report against the criteria above.
Respond with a JSON object:
{{
  "verdict": "sufficient" or "insufficient",
  "gaps": ["gap 1", "gap 2"]
}}

If verdict is "sufficient", gaps should be an empty list.
If verdict is "insufficient", gaps must list the specific missing dimensions that need additional sub-analysis.
Return only the JSON object."""


def report_evaluator(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "report_evaluator"}).eq("task_id", state["task_id"]).execute()

    question     = state["query"]
    draft_report = state.get("draft_report", "")

    prompt = REPORT_EVALUATOR_PROMPT.format(
        question=question,
        report=draft_report,
    )

    result = router.complete(agent="report_evaluator", prompt=prompt)
    text   = result["text"].strip()

    import json, re
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()

    try:
        parsed  = json.loads(text)
        verdict = parsed.get("verdict", "sufficient")
        gaps    = parsed.get("gaps", [])
    except Exception:
        verdict = "sufficient"
        gaps    = []

    print(f"[ReportEvaluator] Verdict: {verdict}, gaps: {gaps}")
    gap_text = f" — gaps: {'; '.join(gaps[:3])}" if gaps else ""
    log_event(state["task_id"], "report_evaluator",
              f"Report quality: {'sufficient ✓' if verdict == 'sufficient' else f'insufficient{gap_text}'}",
              "success" if verdict == "sufficient" else "info",
              {"verdict": verdict, "gaps": gaps, "round": state.get("report_rounds", 0) + 1})

    return {
        "report_verdict": verdict,
        "report_gaps":    gaps,
        "report_rounds":  state.get("report_rounds", 0) + 1,
    }
