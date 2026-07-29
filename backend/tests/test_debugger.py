from unittest.mock import patch, MagicMock
from agents.debugger import debugger


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 20,
        "duration_ms":   800,
        "agent":         "debugger",
        "tier":          "high",
    }


def base_state():
    return {
        "task_id":          "test-123",
        "data_descriptions": {"test.csv": "CSV with columns: amount, currency"},
        "current_script":   "print(undefinde_var)",
        "execution_result": "NameError: name 'undefinde_var' is not defined",
        "debug_attempts":   1,
        "current_round":    0,
    }


def test_debugger_returns_fixed_script_stripped_of_fences():
    with patch("agents.debugger.supabase") as mock_supabase, \
         patch("agents.debugger.log_event"), \
         patch("agents.debugger.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("```python\nprint('fixed')\n```")

        result = debugger(base_state())

    assert result == {"current_script": "print('fixed')"}


def test_debugger_does_not_drop_last_line_when_closing_fence_is_missing():
    with patch("agents.debugger.supabase") as mock_supabase, \
         patch("agents.debugger.log_event"), \
         patch("agents.debugger.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result(
            "```python\nx = 1\nprint(x)"
        )

        result = debugger(base_state())

    assert result["current_script"] == "x = 1\nprint(x)"


def test_debugger_prompt_includes_error_and_prior_script():
    with patch("agents.debugger.supabase") as mock_supabase, \
         patch("agents.debugger.log_event"), \
         patch("agents.debugger.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print('fixed')")

        debugger(base_state())

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "print(undefinde_var)" in prompt
    assert "NameError: name 'undefinde_var' is not defined" in prompt
    assert "test.csv" in prompt
