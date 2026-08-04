import json
from unittest.mock import patch, MagicMock
from agents.report_evaluator import report_evaluator


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  100,
        "output_tokens": 30,
        "duration_ms":   700,
        "agent":         "report_evaluator",
        "tier":          "medium",
    }


def base_state(**overrides):
    state = {
        "task_id":       "test-123",
        "query":         "How is fraud risk distributed across entities?",
        "draft_report":  '{"title": "Fraud Report"}',
        "sub_questions": ["Fraud rate by entity?"],
        "hypotheses":    {"Fraud rate by entity?": "Fraud is concentrated in a few entities."},
        "report_rounds": 0,
    }
    state.update(overrides)
    return state


def test_parses_structured_gaps():
    verdict_json = json.dumps({
        "verdict": "insufficient",
        "gaps": [{"question": "What drives the top entity's fraud rate?", "hypothesis": "It's a single channel."}],
    })
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(verdict_json)

        result = report_evaluator(base_state())

    assert result["report_verdict"] == "insufficient"
    assert result["report_gaps"] == [
        {"question": "What drives the top entity's fraud rate?", "hypothesis": "It's a single channel."}
    ]
    assert result["report_rounds"] == 1


def test_tolerates_plain_string_gaps_from_model():
    verdict_json = json.dumps({"verdict": "insufficient", "gaps": ["Missing driver analysis"]})
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(verdict_json)

        result = report_evaluator(base_state())

    assert result["report_gaps"] == [{"question": "Missing driver analysis", "hypothesis": ""}]


def test_malformed_json_defaults_to_insufficient_with_no_gaps():
    """A parse failure must not silently ship an unevaluated report as 'sufficient' — treat
    it conservatively as insufficient (bounded by max_report_rounds, so it can't loop
    forever) and surface an error-level log entry instead of a false pass."""
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event") as mock_log_event, \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("not json at all")

        result = report_evaluator(base_state())

    assert result["report_verdict"] == "insufficient"
    assert result["report_gaps"] == []
    log_call = mock_log_event.call_args
    assert log_call.args[3] == "error"
    assert log_call.args[4]["parse_failed"] is True


def test_empty_response_defaults_to_insufficient_with_no_gaps():
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("")

        result = report_evaluator(base_state())

    assert result["report_verdict"] == "insufficient"
    assert result["report_gaps"] == []


def test_includes_hypotheses_in_prompt():
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(json.dumps({"verdict": "sufficient", "gaps": []}))

        report_evaluator(base_state())

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Fraud is concentrated in a few entities." in prompt
