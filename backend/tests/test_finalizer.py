from unittest.mock import patch, MagicMock
from agents.finalizer import finalizer


def make_mock_llm_result(text="print('42')"):
    return {
        "text":          text,
        "model":         "gemini-2.5-pro",
        "input_tokens":  50,
        "output_tokens": 10,
        "duration_ms":   1200,
        "agent":         "finalizer",
        "tier":          "medium",
    }


def base_state():
    return {
        "task_id":               "test-123",
        "query":                 "What is the total transaction volume?",
        "formatting_guidelines": "Return a table",
        "data_descriptions":     {"test.csv": "CSV with columns: amount, currency"},
        "current_script":        "print('reference result')",
        "execution_result":      "42",
    }


def test_finalizer_marks_status_completed_on_successful_script():
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print('42')")
        mock_execute.return_value = ("42\n", "", 0)

        result = finalizer(base_state())

        assert result["status"] == "completed"
        assert result["final_result"] == "42\n"


def test_finalizer_marks_status_failed_when_generated_script_errors():
    """Regression test for the finalizer false-success bug: a failing generated
    script must not be reported as a completed task."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("raise ValueError('boom')")
        mock_execute.return_value = ("", "ValueError: boom", 1)

        result = finalizer(base_state())

        assert result["status"] == "failed"
        assert "Execution failed" in result["final_result"]
        assert "boom" in result["final_result"]
