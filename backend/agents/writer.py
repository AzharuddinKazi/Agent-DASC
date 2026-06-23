from agents.state import TaskState
from agents.logger import log_event
from llm_router import LLMRouter
from db import supabase
import json

router = LLMRouter()

WRITER_PROMPT = """You are a senior supervisory analyst writing a formal data science research report.
You have been provided with an open-ended research query and a set of targeted sub-analyses,
each with its own summary, key findings, and data table.

Your task is to synthesise these sub-analyses into a single, well-structured research report.

# Research Query
{question}

# Sub-Analyses
{sub_analyses}

# Report requirements
Write a comprehensive report in the following JSON structure:

{{
  "title": "concise report title",
  "executive_summary": "3-4 sentence executive summary answering the research query directly",
  "sections": [
    {{
      "heading": "Section heading",
      "body": "2-4 paragraph narrative synthesising findings from one or more sub-analyses. Include specific numbers and entity names.",
      "sub_question": "the sub-question this section addresses",
      "key_stat": "the single most important number or fact from this section"
    }}
  ],
  "conclusions": "3-5 sentence conclusion with actionable supervisory recommendations",
  "data_coverage": {{
    "sub_questions_answered": {sub_q_count},
    "total_records_analysed": <integer total rows across all sub-analyses>,
    "datasets_used": [<list of distinct filenames mentioned in sub-analyses>]
  }}
}}

Rules:
- Each section must cite specific numbers, entity names, and findings from the sub-analyses
- Sections must tell a coherent story together, not just list isolated facts
- The executive summary must directly answer the research query
- Conclusions must include concrete supervisory recommendations
- Return only the JSON object, no markdown, no extra text"""


def writer(state: TaskState) -> dict:
    supabase.table("tasks").update({"current_agent": "writer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "writer",
              f"Synthesising report from {len(state.get('sub_results', {}))} sub-analyses...",
              "running", {"sub_q_count": len(state.get("sub_questions", []))})

    question     = state["query"]
    sub_questions = state.get("sub_questions", [])
    sub_results  = state.get("sub_results", {})

    # Build sub-analyses text for the prompt
    sub_analyses_parts = []
    for i, sq in enumerate(sub_questions):
        sr = sub_results.get(sq, {})
        part = f"""### Sub-analysis {i+1}: {sq}
Summary: {sr.get('summary', 'No result')}
Key Findings: {json.dumps(sr.get('key_findings', []))}
Data (columns): {json.dumps(sr.get('columns', []))}
Data (first 5 rows): {json.dumps(sr.get('rows', [])[:5])}"""
        sub_analyses_parts.append(part)

    sub_analyses_text = "\n\n".join(sub_analyses_parts)

    prompt = WRITER_PROMPT.format(
        question=question,
        sub_analyses=sub_analyses_text,
        sub_q_count=len(sub_questions),
    )

    result      = router.complete(agent="writer", prompt=prompt)
    report_text = result["text"].strip()

    # Strip any markdown fences
    import re
    if report_text.startswith("```"):
        report_text = re.sub(r"^```[a-z]*\n?", "", report_text).rstrip("`").strip()

    print(f"[Writer] Report generated ({result['output_tokens']} tokens)")
    log_event(state["task_id"], "writer", "Draft report generated — sending for evaluation", "success")

    return {"draft_report": report_text}
