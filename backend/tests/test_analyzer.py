import os
from unittest.mock import patch, MagicMock
from agents.analyzer import analyze_file, analyzer


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 20,
        "duration_ms":   800,
        "agent":         "analyzer",
        "tier":          "low",
    }


def make_completed_process(stdout="", stderr="", returncode=0):
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def test_analyze_file_strips_code_fence_and_returns_stdout_on_success(tmp_path):
    filepath = tmp_path / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("```python\nprint('columns: a,b')\n```")
        mock_run.return_value = make_completed_process(stdout="columns: a,b", returncode=0)

        description = analyze_file("test.csv", str(filepath), "task-123")

    assert description == "columns: a,b"


def test_analyze_file_returns_failure_message_on_nonzero_exit(tmp_path):
    filepath = tmp_path / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("print(undefined)")
        mock_run.return_value = make_completed_process(stderr="NameError: undefined", returncode=1)

        description = analyze_file("test.csv", str(filepath), "task-123")

    assert description.startswith("Analysis failed:")
    assert "NameError" in description


def test_analyze_file_uses_row_limit_for_large_files(tmp_path):
    filepath = tmp_path / "big.csv"
    filepath.write_text("a,b\n1,2\n")
    # Mocked rather than an actual 300MB+ file on disk — analyze_file only reads the
    # size via os.path.getsize, never the file's own content, for this decision.
    with patch("agents.analyzer.os.path.getsize", return_value=301 * 1024 * 1024), \
         patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("print('ok')")
        mock_run.return_value = make_completed_process(stdout="ok", returncode=0)

        analyze_file("big.csv", str(filepath), "task-123")

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "nrows=10000" in prompt


def test_analyze_file_uses_no_row_limit_under_the_threshold(tmp_path):
    filepath = tmp_path / "medium.csv"
    filepath.write_text("a,b\n1,2\n")
    # 60MB — well under the 300MB threshold (raised 2026-08-23 alongside
    # SANDBOX_MEMORY_LIMIT, see executor.py); used to trigger the row cap at the old
    # 50MB threshold, shouldn't anymore.
    with patch("agents.analyzer.os.path.getsize", return_value=60 * 1024 * 1024), \
         patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("print('ok')")
        mock_run.return_value = make_completed_process(stdout="ok", returncode=0)

        analyze_file("medium.csv", str(filepath), "task-123")

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "nrows=10000" not in prompt
    assert "nrows=all" in prompt


def test_analyze_file_makes_temp_script_world_readable(tmp_path):
    """Same real bug as agents/executor.py's execute_script (see that test's docstring):
    NamedTemporaryFile always creates mode 0600, which the sandbox's non-root UID 1000
    can't read through the :ro mount when this process runs containerized as root."""
    filepath = tmp_path / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run, \
         patch("agents.analyzer.os.unlink") as mock_unlink:
        mock_router.complete.return_value = make_mock_llm_result("print('ok')")
        mock_run.return_value = make_completed_process(stdout="ok", returncode=0)

        analyze_file("test.csv", str(filepath), "task-123")

        args = mock_run.call_args[0][0]
        script_mount = args[args.index("-v") + 3]  # 2nd -v: "<path>:/workspace/scripts/analyze.py:ro"
        script_path = script_mount.split(":")[0]
        mode = os.stat(script_path).st_mode & 0o777

    os.unlink(script_path)
    assert mode == 0o644, f"expected 0644, got {oct(mode)}"


def test_analyze_file_cleans_up_temp_file_even_on_exception(tmp_path):
    filepath = tmp_path / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run", side_effect=RuntimeError("docker down")), \
         patch("agents.analyzer.os.unlink") as mock_unlink:
        mock_router.complete.return_value = make_mock_llm_result("print(1)")
        try:
            analyze_file("test.csv", str(filepath), "task-123")
        except RuntimeError:
            pass

    mock_unlink.assert_called_once()


def base_state():
    return {"task_id": "test-123"}


def test_analyzer_uses_cached_description_when_file_size_matches(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "test.csv").write_text("a,b\n1,2\n")
    file_size = (data_dir / "test.csv").stat().st_size
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"description": "cached description", "file_size_bytes": file_size}]
        )

        result = analyzer(base_state())

    assert result["data_descriptions"]["test.csv"] == "cached description"
    mock_analyze.assert_not_called()


def test_analyzer_reanalyzes_when_cached_size_does_not_match(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "test.csv").write_text("a,b\n1,2\n")
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"description": "stale description", "file_size_bytes": 1}]  # deliberately wrong size
        )
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_analyze.return_value = "fresh description"

        result = analyzer(base_state())

    assert result["data_descriptions"]["test.csv"] == "fresh description"
    mock_analyze.assert_called_once()


def test_analyzer_skips_dotfiles_and_directories(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / ".DS_Store").write_text("junk")
    (data_dir / "subdir").mkdir()
    (data_dir / "real.csv").write_text("a,b\n1,2\n")
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_analyze.return_value = "desc"

        result = analyzer(base_state())

    assert list(result["data_descriptions"].keys()) == ["real.csv"]
