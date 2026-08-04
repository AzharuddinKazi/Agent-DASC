import json
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


def test_finalizer_retries_a_syntax_error_with_a_fresh_generation_not_a_patch():
    """Regression test: a SyntaxError almost always means the previous generation was
    cut off mid-token (e.g. an unterminated string literal), not a logic bug to patch —
    feeding the already-truncated fragment back into the debugger prompt as "code to
    fix" tends to just reproduce the same truncation. Must re-run the original,
    complete finalizer prompt fresh instead of routing through the debugger."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.side_effect = [
            make_mock_llm_result("outpatient_df = pd.read_csv('/workspace/data/medicare"),  # truncated
            make_mock_llm_result("print('42')"),                                             # fresh retry
        ]
        mock_execute.side_effect = [
            ("", "  File \"step.py\", line 1\nSyntaxError: unterminated string literal", 1),
            ("42\n", "", 0),
        ]

        result = finalizer(base_state())

    assert result["status"] == "completed"
    assert result["final_result"] == "42\n"
    retry_call = mock_router.complete.call_args_list[1]
    assert retry_call.kwargs["agent"] == "finalizer"
    assert retry_call.kwargs["prompt"] == mock_router.complete.call_args_list[0].kwargs["prompt"]


def test_finalizer_injects_real_debug_attempts_and_files_used_into_json_output():
    """Regression test for the fabricated-stats bug: the Insight dashboard used to show a
    client-side guessed token/cost estimate because no real provenance reached the
    frontend at all. This is that real signal — attempt count and actual profiled
    filenames, injected server-side rather than trusted to the LLM."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result('{"summary": "ok"}')
        mock_execute.return_value = ('{"summary": "ok"}', "", 0)

        state = base_state()
        state["data_descriptions"] = {"a.csv": "desc a", "b.csv": "desc b"}
        result = finalizer(state)

    parsed = json.loads(result["final_result"])
    assert parsed["summary"] == "ok"
    assert parsed["debug_attempts"] == 0
    assert parsed["files_used"] == ["a.csv", "b.csv"]


def test_finalizer_records_nonzero_debug_attempts_after_a_retry():
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.side_effect = [
            make_mock_llm_result("raise ValueError('boom')"),
            make_mock_llm_result('{"summary": "fixed"}'),
        ]
        mock_execute.side_effect = [
            ("", "ValueError: boom", 1),
            ('{"summary": "fixed"}', "", 0),
        ]

        result = finalizer(base_state())

    parsed = json.loads(result["final_result"])
    assert parsed["debug_attempts"] == 1


def test_finalizer_leaves_non_json_output_untouched():
    """No dict to attach provenance to — must not crash or mangle plain-text output."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print('42')")
        mock_execute.return_value = ("42\n", "", 0)

        result = finalizer(base_state())

    assert result["final_result"] == "42\n"


def test_finalizer_strips_internal_file_paths_from_a_multiline_traceback():
    """Regression test: final_result is served directly through GET /api/v1/get_task and
    rendered verbatim in the frontend's failure view — a raw multi-line traceback
    exposes internal container file paths and library internals there. Only the final
    "ExceptionType: message" line should survive into final_result."""
    traceback_text = (
        "Traceback (most recent call last):\n"
        '  File "/workspace/scripts/step.py", line 5, in <module>\n'
        "    df['x'].astype(float)\n"
        "ValueError: could not convert string to float: 'N/A'"
    )
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("df['x'].astype(float)")
        mock_execute.side_effect = [("", traceback_text, 1)] * 3

        result = finalizer(base_state())

    assert result["final_result"] == "Execution failed: ValueError: could not convert string to float: 'N/A'"
    assert "/workspace/scripts/step.py" not in result["final_result"]


def test_finalizer_logs_warning_on_schema_mismatch_but_still_ships_output(caplog):
    """Schema validation is visibility-only — output missing the expected "summary" field
    still reaches final_result unchanged, it's just logged so the mismatch isn't a mystery
    later on the frontend."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result('{"foo": "bar"}')
        mock_execute.return_value = ('{"foo": "bar"}', "", 0)

        with caplog.at_level("WARNING"):
            result = finalizer(base_state())

    parsed = json.loads(result["final_result"])
    assert parsed["foo"] == "bar"
    assert "doesn't match expected schema" in caplog.text


def test_finalizer_sanitizes_nan_so_frontend_json_parse_never_sees_it():
    """Regression test: Python's json module accepts bare NaN/Infinity tokens on both
    dump and parse, but the frontend's spec-compliant JSON.parse rejects them outright,
    losing the structured view for an otherwise-successful result. A generated script
    emitting a NaN (e.g. from an unfilled pandas mean()) must not leak it into
    final_result."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print('{\"summary\": \"ok\", \"rows\": [[1, NaN]]}')")
        mock_execute.return_value = ('{"summary": "ok", "rows": [[1, NaN]]}', "", 0)

        result = finalizer(base_state())

    assert "NaN" not in result["final_result"]
    parsed = json.loads(result["final_result"])
    assert parsed["rows"] == [[1, None]]


def test_finalizer_leaves_non_json_scalar_output_byte_for_byte_unchanged():
    """A scalar JSON value with no NaN/Infinity token must not be re-serialized —
    re-dumping unconditionally would silently reformat whitespace (e.g. drop a
    trailing newline) for output that never needed touching."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print(42)")
        mock_execute.return_value = ("42\n", "", 0)

        result = finalizer(base_state())

    assert result["final_result"] == "42\n"


def test_finalizer_sanitizes_nan_in_a_non_dict_json_output():
    """A bare NaN can also appear in a top-level JSON list/scalar, not just an object —
    e.g. a script that prints a raw list of rows. Must be sanitized the same way."""
    with patch("agents.finalizer.supabase") as mock_supabase, \
         patch("agents.finalizer.log_event"), \
         patch("agents.finalizer.router") as mock_router, \
         patch("agents.finalizer.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("print('[1, NaN, 3]')")
        mock_execute.return_value = ("[1, NaN, 3]", "", 0)

        result = finalizer(base_state())

    assert result["final_result"] == "[1, null, 3]"


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
