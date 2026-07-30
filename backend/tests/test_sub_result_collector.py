from unittest.mock import patch, MagicMock
from agents.graph import sub_result_collector


def base_state(**overrides):
    state = {
        "task_id":          "test-123",
        "sub_questions":    ["What is the mean age?"],
        "current_sub_idx":  0,
        "sub_results":      {},
        "execution_result": "",
        "final_result":     None,
    }
    state.update(overrides)
    return state


def test_dict_shaped_result_stored_as_is():
    state = base_state(execution_result='{"summary": "Mean age is 71.55", "key_findings": [], "columns": [], "rows": []}')
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sub_result_collector(state)

    assert result["sub_results"]["What is the mean age?"]["summary"] == "Mean age is 71.55"


def test_bare_number_result_falls_back_to_summary_dict():
    """Regression test: a script that prints a bare number (e.g. "71.55") is valid JSON
    (a float, not an object) — json.loads succeeds, so the old code stored a raw float in
    sub_results, which then crashed writer.py's sr.get("summary", ...) with
    AttributeError: 'float' object has no attribute 'get'. Must fall back to the
    summary-dict shape for any non-dict JSON value, same as a JSON parse failure."""
    state = base_state(execution_result="71.55")
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sub_result_collector(state)

    stored = result["sub_results"]["What is the mean age?"]
    assert isinstance(stored, dict)
    assert stored["summary"] == "71.55"


def test_bare_list_result_falls_back_to_summary_dict():
    state = base_state(execution_result="[1, 2, 3]")
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sub_result_collector(state)

    stored = result["sub_results"]["What is the mean age?"]
    assert isinstance(stored, dict)
    assert stored["summary"] == "[1, 2, 3]"


def test_non_json_result_falls_back_to_summary_dict():
    state = base_state(execution_result="Mean age: 71.55 years")
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sub_result_collector(state)

    stored = result["sub_results"]["What is the mean age?"]
    assert stored == {"summary": "Mean age: 71.55 years", "key_findings": [], "columns": [], "rows": []}


def test_exit_code_nonzero_records_an_explicit_failure_not_the_raw_traceback():
    """Regression test: arriving here via route_after_executor's debug-exhaustion
    branch (a sub-question that never ran successfully) used to store the raw Python
    traceback as the sub-question's "summary" — which the writer would then cite as if
    it were a real finding. Must be recorded as an explicit, clean failure instead."""
    state = base_state(
        exit_code=1,
        execution_result="Traceback (most recent call last):\n  ...\nKeyError: 'X'",
    )
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event") as mock_log_event:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = sub_result_collector(state)

    stored = result["sub_results"]["What is the mean age?"]
    assert stored["failed"] is True
    assert "Traceback" not in stored["summary"]
    assert "KeyError" not in stored["summary"]

    log_call = mock_log_event.call_args
    assert "failed" in log_call[0][2].lower()
    assert log_call[0][3] == "error"
