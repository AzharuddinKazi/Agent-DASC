import json
from unittest.mock import patch, MagicMock
from agents.writer import writer


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 10,
        "duration_ms":   1200,
        "agent":         "writer",
        "tier":          "medium",
    }


def base_state():
    return {
        "task_id":       "test-123",
        "query":         "How is fraud risk distributed across entities?",
        "domain_pack_id": None,
        "sub_questions": [
            "What is the fraud rate by entity?",
            "Which channels see the most fraud?",
        ],
        "sub_results": {
            "What is the fraud rate by entity?": {
                "summary": "Entity-07 has the highest fraud rate at 8.3%.",
                "key_findings": ["Entity-07: 8.3%"],
                "columns": ["entity", "fraud_rate"],
                "rows": [["Entity-07", 0.083]],
            },
            "Which channels see the most fraud?": {
                "summary": "Online channel accounts for 61% of fraud cases.",
                "key_findings": ["Online: 61%"],
                "columns": ["channel", "fraud_share"],
                "rows": [["Online", 0.61]],
            },
        },
    }


def report_json(**overrides):
    base = {
        "title": "Fraud Risk Report",
        "executive_summary": "Entity-07 leads fraud risk at 8.3% [1].",
        "sections": [{"heading": "Findings", "body": "Online fraud dominates [2].", "key_stat": "61% online [2]"}],
        "risk_matrix": [],
        "conclusions": "Focus on Entity-07 and online channel [1,2].",
        "recommendations": ["Investigate Entity-07"],
        "data_coverage": {"sub_questions_answered": 2, "total_records_analysed": 2, "datasets_used": ["test.csv"]},
    }
    base.update(overrides)
    return json.dumps(base)


def test_writer_attaches_sources_matching_sub_questions_in_order():
    with patch("agents.writer.supabase") as mock_supabase, \
         patch("agents.writer.log_event"), \
         patch("agents.writer.router") as mock_router, \
         patch("agents.writer.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"report_persona": "You are an analyst.", "report_classification": None}
        mock_router.complete.return_value = make_mock_llm_result(report_json())

        result = writer(base_state())
        report = json.loads(result["draft_report"])

    assert report["sources"] == [
        {"id": 1, "question": "What is the fraud rate by entity?",
         "summary": "Entity-07 has the highest fraud rate at 8.3%."},
        {"id": 2, "question": "Which channels see the most fraud?",
         "summary": "Online channel accounts for 61% of fraud cases."},
    ]


def test_writer_ignores_llm_provided_sources_field():
    """The LLM is told not to invent a sources field — even if it does, the
    server-computed list must win, since it's the only guaranteed-correct one."""
    with patch("agents.writer.supabase") as mock_supabase, \
         patch("agents.writer.log_event"), \
         patch("agents.writer.router") as mock_router, \
         patch("agents.writer.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"report_persona": "You are an analyst.", "report_classification": None}
        mock_router.complete.return_value = make_mock_llm_result(
            report_json(sources=[{"id": 99, "question": "hallucinated", "summary": "wrong"}])
        )

        result = writer(base_state())
        report = json.loads(result["draft_report"])

    assert report["sources"][0]["id"] == 1
    assert report["sources"][0]["question"] == "What is the fraud rate by entity?"


def test_writer_survives_non_json_output_without_crashing():
    with patch("agents.writer.supabase") as mock_supabase, \
         patch("agents.writer.log_event"), \
         patch("agents.writer.router") as mock_router, \
         patch("agents.writer.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"report_persona": "You are an analyst.", "report_classification": None}
        mock_router.complete.return_value = make_mock_llm_result("not valid json at all")

        result = writer(base_state())

    assert result["draft_report"] == "not valid json at all"
