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


def test_overrides_sufficient_verdict_when_a_sub_result_is_structurally_thin():
    """Regression test: a report can read as coherent prose (and get judged 'sufficient'
    by the evaluator's own LLM call) while actually being built on a sub-analysis with no
    real structured findings — confirmed live, where a report was accepted as sufficient
    on the first pass despite every one of its 6 sub-analyses having empty
    key_findings/rows. This is a deterministic backstop independent of the LLM's
    judgment of the rendered report text."""
    state = base_state(sub_results={
        "Fraud rate by entity?": {
            "summary": "Entity-07 has a 3.2% dtype: float64\nmean 0.032...",  # raw dump
            "key_findings": [], "rows": [], "columns": [],
        }
    })
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event") as mock_log_event, \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(json.dumps({"verdict": "sufficient", "gaps": []}))

        result = report_evaluator(state)

    assert result["report_verdict"] == "insufficient"
    assert len(result["report_gaps"]) == 1
    assert "Fraud rate by entity?" in result["report_gaps"][0]["question"]
    assert result["report_gaps"][0]["question"] != "Fraud rate by entity?"  # must not collide with the original key
    log_call = mock_log_event.call_args
    assert log_call.args[4]["structurally_thin_sub_results"] == ["Fraud rate by entity?"]


def test_does_not_override_verdict_when_sub_results_have_real_structure():
    state = base_state(sub_results={
        "Fraud rate by entity?": {
            "summary": "Entity-07 leads at 3.2%.",
            "key_findings": ["Entity-07: 3.2%"], "rows": [["Entity-07", 0.032]], "columns": ["entity", "rate"],
        }
    })
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(json.dumps({"verdict": "sufficient", "gaps": []}))

        result = report_evaluator(state)

    assert result["report_verdict"] == "sufficient"
    assert result["report_gaps"] == []


def test_does_not_flag_an_already_recorded_failure_as_structurally_thin():
    """A sub-question that failed outright (debug retries exhausted) is already recorded
    as failed=True with an explanatory summary — a separate, already-visible failure
    mode, not the silent-empty-structure case this backstop targets."""
    state = base_state(sub_results={
        "Fraud rate by entity?": {
            "summary": "This sub-question could not be answered — the analysis script failed.",
            "key_findings": [], "rows": [], "columns": [], "failed": True,
        }
    })
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(json.dumps({"verdict": "sufficient", "gaps": []}))

        result = report_evaluator(state)

    assert result["report_verdict"] == "sufficient"


def test_includes_hypotheses_in_prompt():
    with patch("agents.report_evaluator.supabase") as mock_supabase, \
         patch("agents.report_evaluator.log_event"), \
         patch("agents.report_evaluator.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(json.dumps({"verdict": "sufficient", "gaps": []}))

        report_evaluator(base_state())

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Fraud is concentrated in a few entities." in prompt
