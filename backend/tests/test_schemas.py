from agents.schemas import FinalizerOutput, WriterReport, validate_and_log


def test_valid_finalizer_output_passes():
    parsed = {
        "summary": "Entity-07 leads.",
        "key_findings": ["Entity-07: 8.3%"],
        "columns": ["entity", "rate"],
        "rows": [["Entity-07", 0.083]],
        "chart": None,
        "raw": "Entity-07 leads at 8.3%.",
    }
    assert validate_and_log(FinalizerOutput, parsed, task_id="t1", agent="finalizer") is True


def test_finalizer_output_missing_required_field_fails(caplog):
    parsed = {"key_findings": [], "columns": [], "rows": []}  # no "summary"
    with caplog.at_level("WARNING"):
        ok = validate_and_log(FinalizerOutput, parsed, task_id="t1", agent="finalizer")
    assert ok is False
    assert "summary" in caplog.text


def test_finalizer_output_wrong_type_fails(caplog):
    parsed = {"summary": "ok", "rows": "not-a-list-of-rows"}
    with caplog.at_level("WARNING"):
        ok = validate_and_log(FinalizerOutput, parsed, task_id="t1", agent="finalizer")
    assert ok is False


def test_valid_writer_report_passes():
    parsed = {
        "title": "Fraud Risk Report",
        "executive_summary": "Entity-07 leads fraud risk.",
        "sections": [{"heading": "Findings", "body": "Details.", "key_stat": "8.3%"}],
        "risk_matrix": [],
        "conclusions": "Focus on Entity-07.",
        "recommendations": ["Investigate Entity-07"],
        "data_coverage": {"sub_questions_answered": 1, "total_records_analysed": 1, "datasets_used": ["x.csv"]},
    }
    assert validate_and_log(WriterReport, parsed, task_id="t1", agent="writer") is True


def test_writer_report_missing_required_field_fails(caplog):
    parsed = {"executive_summary": "no title here", "sections": []}
    with caplog.at_level("WARNING"):
        ok = validate_and_log(WriterReport, parsed, task_id="t1", agent="writer")
    assert ok is False
    assert "title" in caplog.text
