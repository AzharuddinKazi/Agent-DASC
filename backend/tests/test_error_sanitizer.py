from agents.error_sanitizer import summarize_script_failure, GENERIC_INFRASTRUCTURE_ERROR


def test_extracts_the_final_exception_line_from_a_real_traceback():
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "/workspace/scripts/step.py", line 12, in <module>\n'
        "    df['x'].astype(float)\n"
        '  File "/usr/local/lib/python3.12/site-packages/pandas/core/series.py", line 900, in astype\n'
        "    return self._astype(dtype)\n"
        "ValueError: could not convert string to float: 'N/A'"
    )
    result = summarize_script_failure(stderr)
    assert result == "ValueError: could not convert string to float: 'N/A'"
    assert "/workspace/scripts/step.py" not in result
    assert "pandas/core/series.py" not in result


def test_handles_a_single_line_error():
    assert summarize_script_failure("ValueError: boom") == "ValueError: boom"


def test_handles_empty_stderr():
    assert summarize_script_failure("") == "The generated script failed with no error output."


def test_handles_whitespace_only_stderr():
    assert summarize_script_failure("   \n  \n") == "The generated script failed with no error output."


def test_generic_infrastructure_error_message_does_not_leak_exception_detail():
    assert "Traceback" not in GENERIC_INFRASTRUCTURE_ERROR
    assert len(GENERIC_INFRASTRUCTURE_ERROR) < 200
