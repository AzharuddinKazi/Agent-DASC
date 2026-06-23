from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
import json

router = LLMRouter()

WRITER_PROMPT = """You are a senior regulatory analyst at a central bank writing an official supervisory report.
You have completed {sub_q_count} targeted data analyses. Your job is to synthesise these into a
formal, publication-quality supervisory report — NOT a list of data summaries.

# Research Query (the report must answer this)
{question}

# Completed Sub-Analyses
{sub_analyses}

# Report Writing Rules
1. SYNTHESISE, don't list. Each section must weave findings from multiple sub-analyses into a
   coherent narrative. A section is NOT a summary of one sub-question — it is a thematic argument
   supported by data from across the analyses.
2. CITE numbers precisely. Every claim must be backed by a specific figure from the data
   (e.g. "LFI-07 recorded a fraud rate of 8.3%, nearly 3× the sector average of 2.9%").
3. USE formal supervisory language. Avoid casual phrasing. Write as if this will be read
   by a board of directors or a regulatory committee.
4. STRUCTURE thematically. Group related findings under risk categories
   (e.g. Transaction Risk, Compliance Risk, Operational Risk), not by sub-question.
5. RECOMMEND actions. The conclusions section must end with 3-5 specific, actionable
   supervisory recommendations addressed to institution management.

# Required Output Format (strict JSON — return ONLY this, no markdown fences)
{{
  "title": "Formal report title (e.g. 'Supervisory Risk Assessment: AML & Fraud Exposure Across Licensed Financial Institutions')",
  "classification": "SUPERVISORY — CONFIDENTIAL",
  "reporting_period": "Based on available transaction data",
  "executive_summary": "4-6 sentences. State the most critical findings directly. Name the worst-performing entities. Quantify the risk. End with the overall supervisory stance.",
  "sections": [
    {{
      "heading": "Thematic section heading (e.g. '1. Fraud Risk and Transaction Integrity')",
      "body": "3-5 paragraphs of formal narrative. Must include specific LFI names/IDs, exact figures, comparisons to benchmarks, and cross-references to other risk dimensions. Use markdown for emphasis: **bold** for key entities, `code` for metric names.",
      "key_stat": "Single most important number from this section (e.g. 'Sector fraud rate: 4.2%')"
    }}
  ],
  "risk_matrix": [
    {{
      "entity": "LFI name or ID",
      "fraud_risk": "High / Medium / Low",
      "compliance_risk": "High / Medium / Low",
      "operational_risk": "High / Medium / Low",
      "overall": "High / Medium / Low",
      "priority_action": "One-line recommended action"
    }}
  ],
  "conclusions": "5-7 sentences summarising overall supervisory findings and the urgency of action required.",
  "recommendations": [
    "Specific recommendation 1 addressed to a named entity or all LFIs",
    "Specific recommendation 2",
    "Specific recommendation 3"
  ],
  "data_coverage": {{
    "sub_questions_answered": {sub_q_count},
    "total_records_analysed": <integer — sum of row counts from all sub-analyses>,
    "datasets_used": [<list of distinct CSV filenames referenced in the analyses>]
  }}
}}"""


def writer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "writer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "writer",
              f"Synthesising report from {len(state.get('sub_results', {}))} sub-analyses...",
              "running", {"sub_q_count": len(state.get("sub_questions", []))})

    question      = state["query"]
    sub_questions = state.get("sub_questions", [])
    sub_results   = state.get("sub_results", {})

    sub_analyses_parts = []
    for i, sq in enumerate(sub_questions):
        sr = sub_results.get(sq, {})
        part = f"""### Analysis {i+1}: {sq}
Summary: {sr.get('summary', 'No result available')}
Key Findings: {json.dumps(sr.get('key_findings', []), indent=2)}
Columns: {json.dumps(sr.get('columns', []))}
Data rows (first 8): {json.dumps(sr.get('rows', [])[:8])}"""
        sub_analyses_parts.append(part)

    sub_analyses_text = "\n\n".join(sub_analyses_parts)

    prompt = WRITER_PROMPT.format(
        question=question,
        sub_analyses=sub_analyses_text,
        sub_q_count=len(sub_questions),
    )

    result      = router.complete(agent="writer", prompt=prompt)
    report_text = result["text"].strip()

    import re
    if report_text.startswith("```"):
        report_text = re.sub(r"^```[a-z]*\n?", "", report_text).rstrip("`").strip()

    print(f"[Writer] Report generated ({result['output_tokens']} tokens)")
    log_event(state["task_id"], "writer", "Draft report generated — sending for evaluation", "success")

    return {"draft_report": report_text}
