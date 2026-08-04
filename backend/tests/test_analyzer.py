import os
from unittest.mock import patch, MagicMock
from agents.analyzer import analyze_file, analyzer, _content_fingerprint


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
    filepath.write_bytes(b"0" * (60 * 1024 * 1024))  # 60MB, over the 50MB threshold
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("print('ok')")
        mock_run.return_value = make_completed_process(stdout="ok", returncode=0)

        analyze_file("big.csv", str(filepath), "task-123")

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "nrows=10000" in prompt


def test_analyze_file_invokes_docker_with_sandbox_hardening_flags(tmp_path):
    filepath = tmp_path / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    with patch("agents.analyzer.router") as mock_router, \
         patch("agents.analyzer.subprocess.run") as mock_run:
        mock_router.complete.return_value = make_mock_llm_result("print('ok')")
        mock_run.return_value = make_completed_process(stdout="ok", returncode=0)

        analyze_file("test.csv", str(filepath), "task-123")

        args = mock_run.call_args[0][0]

    assert "--network=none" in args
    assert "--read-only" in args
    assert "--cap-drop" in args
    assert "--pids-limit" in args


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


def test_analyzer_uses_cached_description_when_size_and_hash_match(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    filepath = data_dir / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    file_size = filepath.stat().st_size
    content_hash = _content_fingerprint(str(filepath), file_size)
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"description": "cached description", "file_size_bytes": file_size, "content_hash": content_hash}]
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
            data=[{"description": "stale description", "file_size_bytes": 1, "content_hash": "irrelevant"}]  # deliberately wrong size
        )
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_analyze.return_value = "fresh description"

        result = analyzer(base_state())

    assert result["data_descriptions"]["test.csv"] == "fresh description"
    mock_analyze.assert_called_once()


def test_analyzer_reanalyzes_on_same_name_and_size_but_different_content(tmp_path):
    """Regression test for the actual gap this closes: a same-name-different-content file
    that happens to share a byte count with whatever was cached must not serve the wrong
    dataset's description."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    filepath = data_dir / "test.csv"
    filepath.write_text("a,b\n9,9\n")  # same length as "a,b\n1,2\n", different content
    file_size = filepath.stat().st_size
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"description": "wrong dataset's cached description", "file_size_bytes": file_size,
                   "content_hash": "not-the-real-hash"}]
        )
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_analyze.return_value = "fresh description"

        result = analyzer(base_state())

    assert result["data_descriptions"]["test.csv"] == "fresh description"
    mock_analyze.assert_called_once()


def test_analyzer_reanalyzes_when_cached_row_predates_content_hash_column(tmp_path):
    """Old cache rows written before this migration have no content_hash — must miss the
    cache once (safe default: re-analyze) rather than trust a size-only match."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    filepath = data_dir / "test.csv"
    filepath.write_text("a,b\n1,2\n")
    file_size = filepath.stat().st_size
    with patch.dict(os.environ, {"DSSTAR": str(tmp_path)}), \
         patch("agents.analyzer.supabase") as mock_supabase, \
         patch("agents.analyzer.log_event"), \
         patch("agents.analyzer.analyze_file") as mock_analyze:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"description": "old cached description", "file_size_bytes": file_size}]  # no content_hash key
        )
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_analyze.return_value = "fresh description"

        result = analyzer(base_state())

    assert result["data_descriptions"]["test.csv"] == "fresh description"
    mock_analyze.assert_called_once()


def test_content_fingerprint_differs_for_same_size_different_content(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("a,b\n1,2\n")
    b.write_text("a,b\n9,9\n")
    assert a.stat().st_size == b.stat().st_size
    assert _content_fingerprint(str(a), a.stat().st_size) != _content_fingerprint(str(b), b.stat().st_size)


def test_content_fingerprint_stable_for_identical_content(tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("a,b\n1,2\n")
    size = a.stat().st_size
    assert _content_fingerprint(str(a), size) == _content_fingerprint(str(a), size)


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
