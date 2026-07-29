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
        # side_effect (not return_value) — a fixed return_value would make the retry
        # loop's later iterations invisible: it "fails" the same way whether or not the
        # loop actually ran, so this couldn't tell a real retry from a no-op.
        mock_execute.side_effect = [("", "ValueError: boom", 1)] * 3

        result = finalizer(base_state())

        assert result["status"] == "failed"
        assert "Execution failed" in result["final_result"]
        assert "boom" in result["final_result"]
        # Initial attempt + MAX_FINALIZER_DEBUG_ATTEMPTS retries, no more.
        assert mock_execute.call_count == 3


def test_finalizer_recovers_after_one_debug_attempt():
    """The self-debug loop's whole purpose is recovering from a bad first script — this
    was previously untested, so a broken retry (e.g. one that never re-executes the
    debugger's fix) could regress silently."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.side_effect = [
            make_mock_llm_result("raise ValueError('boom')"),  # initial finalizer script
            make_mock_llm_result("print('fixed')"),             # debugger's fix
        ]
        mock_execute.side_effect = [
            ("", "ValueError: boom", 1),
            ("fixed\n", "", 0),
        ]

        result = finalizer(base_state())

    assert result["status"] == "completed"
    assert result["final_result"] == "fixed\n"
    assert mock_execute.call_count == 2
    assert mock_router.complete.call_args_list[1].kwargs["agent"] == "debugger"


def test_finalizer_strips_code_fence_even_when_closing_fence_is_missing():
    """Same bug class as the coder.py fix: a cut-off model response with no closing
    ``` used to silently drop the last real line of the generated script."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(
            "```python\nimport json\nprint(json.dumps({'summary': 'ok'}))"
        )
        mock_execute.return_value = ('{"summary": "ok"}\n', "", 0)

        finalizer(base_state())

        executed_script = mock_execute.call_args[0][0]

    assert executed_script == "import json\nprint(json.dumps({'summary': 'ok'}))"
