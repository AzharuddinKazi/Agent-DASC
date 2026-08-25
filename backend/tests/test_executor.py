import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from agents.executor import execute_script, executor, SANDBOX_MEMORY_LIMIT
from agents.cancellation import TaskCancelled, TaskPaused


def make_mock_proc(returncode=0, communicate_result=("", ""), communicate_side_effect=None):
    proc = MagicMock()
    if communicate_side_effect is not None:
        proc.communicate.side_effect = communicate_side_effect
    else:
        proc.communicate.return_value = communicate_result
    proc.returncode = returncode
    return proc


def test_execute_script_returns_stdout_stderr_and_exit_code_on_success():
    with patch("agents.executor.subprocess.Popen") as mock_popen:
        mock_popen.return_value = make_mock_proc(returncode=0, communicate_result=("42\n", ""))

        stdout, stderr, exit_code = execute_script("print(42)")

    assert stdout == "42\n"
    assert stderr == ""
    assert exit_code == 0


def test_execute_script_invokes_docker_with_expected_flags():
    with patch.dict(os.environ, {"DSSTAR": "/repo"}), \
         patch("agents.executor.subprocess.Popen") as mock_popen:
        mock_popen.return_value = make_mock_proc()

        execute_script("print(1)")

        args = mock_popen.call_args[0][0]

    assert args[0:2] == ["docker", "run"]
    assert "--network=none" in args
    assert f"--memory={SANDBOX_MEMORY_LIMIT}" in args
    assert "/repo/data:/workspace/data:ro" in "".join(args)
    assert "dsstar-sandbox:latest" in args
    assert "--name" in args
    container_name = args[args.index("--name") + 1]
    assert container_name.startswith("dsstar-exec-")


def test_execute_script_makes_temp_script_world_readable():
    """Regression test for a real bug hit live: NamedTemporaryFile always creates the file
    mode 0600, owned by whatever UID this process runs as. When the backend runs
    containerized (root, no USER in backend/Dockerfile) but dsstar-sandbox runs as UID 1000
    (`app`, sandbox/Dockerfile's USER app), the sibling container couldn't read its own
    read-only-mounted script at all — "python3: can't open file ...: [Errno 13] Permission
    denied", exit code 2, on every single script execution. Checks the real file's mode on
    disk (not mocked) since this is exactly the kind of bug a mocked os.chmod call would
    hide. execute_script unlinks the file in its `finally` block, so os.unlink is patched
    here to inspect the mode before that happens, then unlink for real once done.
    """
    with patch("agents.executor.subprocess.Popen") as mock_popen, \
         patch("agents.executor.os.unlink") as mock_unlink:
        mock_popen.return_value = make_mock_proc()
        execute_script("print(1)")

        args = mock_popen.call_args[0][0]
        script_mount = args[args.index("-v") + 3]  # 2nd -v: "<path>:/workspace/scripts/step.py:ro"
        script_path = script_mount.split(":")[0]
        mode = os.stat(script_path).st_mode & 0o777

    os.unlink(script_path)
    assert mode == 0o644, f"expected 0644, got {oct(mode)}"


def test_execute_script_cleans_up_temp_file_even_on_exception():
    with patch("agents.executor.subprocess.Popen", side_effect=RuntimeError("docker daemon down")), \
         patch("agents.executor.os.unlink") as mock_unlink:
        try:
            execute_script("print(1)")
        except RuntimeError:
            pass

    mock_unlink.assert_called_once()


def test_execute_script_truncates_stdout_and_stderr():
    with patch("agents.executor.subprocess.Popen") as mock_popen:
        mock_popen.return_value = make_mock_proc(communicate_result=("a" * 60_000, "b" * 5_000))

        stdout, stderr, _ = execute_script("print(1)")

    assert len(stdout) == 50_000
    assert len(stderr) == 2_000


def test_execute_script_kills_container_and_raises_when_stop_requested():
    """The whole point of polling instead of a single blocking subprocess.run: a Stop
    click must take effect within POLL_INTERVAL_S, not wait out the full 120s timeout."""
    proc = make_mock_proc(communicate_side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=0.5))
    with patch("agents.executor.subprocess.Popen") as mock_popen, \
         patch("agents.executor.subprocess.run") as mock_run, \
         patch("agents.executor.is_cancelled", return_value=True):
        mock_popen.return_value = proc

        with pytest.raises(TaskCancelled):
            execute_script("print(1)", task_id="task-123")

        popen_args = mock_popen.call_args[0][0]
        container_name = popen_args[popen_args.index("--name") + 1]

    mock_run.assert_called_once_with(["docker", "kill", container_name], capture_output=True)
    proc.wait.assert_called_once_with(timeout=5)


def test_execute_script_kills_container_and_raises_when_pause_requested():
    proc = make_mock_proc(communicate_side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=0.5))
    with patch("agents.executor.subprocess.Popen") as mock_popen, \
         patch("agents.executor.subprocess.run") as mock_run, \
         patch("agents.executor.is_cancelled", return_value=False), \
         patch("agents.executor.is_paused", return_value=True):
        mock_popen.return_value = proc

        with pytest.raises(TaskPaused):
            execute_script("print(1)", task_id="task-123")

        popen_args = mock_popen.call_args[0][0]
        container_name = popen_args[popen_args.index("--name") + 1]

    mock_run.assert_called_once_with(["docker", "kill", container_name], capture_output=True)
    proc.wait.assert_called_once_with(timeout=5)


def test_execute_script_checks_cancellation_before_pause():
    """If somehow both are set, Stop should win — matches cancellation.check_interrupt's
    own priority order, kept consistent here too."""
    proc = make_mock_proc(communicate_side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=0.5))
    with patch("agents.executor.subprocess.Popen") as mock_popen, \
         patch("agents.executor.subprocess.run"), \
         patch("agents.executor.is_cancelled", return_value=True), \
         patch("agents.executor.is_paused", return_value=True):
        mock_popen.return_value = proc

        with pytest.raises(TaskCancelled):
            execute_script("print(1)", task_id="task-123")


def test_execute_script_does_not_check_cancellation_when_no_task_id_given():
    """Callers that don't pass task_id (none currently, but the parameter is optional)
    must not crash on a None task_id — is_cancelled should simply never be consulted."""
    proc = make_mock_proc(communicate_result=("ok\n", ""))
    with patch("agents.executor.subprocess.Popen", return_value=proc), \
         patch("agents.executor.is_cancelled") as mock_is_cancelled:
        stdout, _, _ = execute_script("print(1)")

    assert stdout == "ok\n"
    mock_is_cancelled.assert_not_called()


def test_execute_script_kills_container_and_raises_timeout_on_deadline_exceeded():
    proc = make_mock_proc(communicate_side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=0.5))
    with patch("agents.executor.subprocess.Popen") as mock_popen, \
         patch("agents.executor.subprocess.run") as mock_run, \
         patch("agents.executor.is_cancelled", return_value=False), \
         patch("agents.executor.time.monotonic", side_effect=[0, 200]):
        mock_popen.return_value = proc

        with pytest.raises(subprocess.TimeoutExpired):
            execute_script("print(1)")

    mock_run.assert_called_once()
    assert mock_run.call_args[0][0][0:2] == ["docker", "kill"]


def base_state():
    return {
        "task_id":          "test-123",
        "current_script":   "print(42)",
        "current_round":    0,
    }


def test_executor_success_resets_debug_attempts_to_zero():
    with patch("agents.executor.supabase") as mock_supabase, \
         patch("agents.executor.log_event"), \
         patch("agents.executor.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_execute.return_value = ("42\n", "", 0)

        state = base_state()
        state["debug_attempts"] = 3
        result = executor(state)

    assert result == {"execution_result": "42\n", "exit_code": 0, "debug_attempts": 0}


def test_executor_failure_increments_debug_attempts_and_uses_stderr_as_result():
    with patch("agents.executor.supabase") as mock_supabase, \
         patch("agents.executor.log_event"), \
         patch("agents.executor.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_execute.return_value = ("", "Traceback: boom", 1)

        state = base_state()
        state["debug_attempts"] = 1
        result = executor(state)

    assert result == {"execution_result": "Traceback: boom", "exit_code": 1, "debug_attempts": 2}


def test_executor_defaults_debug_attempts_to_zero_when_absent():
    with patch("agents.executor.supabase") as mock_supabase, \
         patch("agents.executor.log_event"), \
         patch("agents.executor.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_execute.return_value = ("", "boom", 1)

        result = executor(base_state())

    assert result["debug_attempts"] == 1


def test_executor_passes_task_id_to_execute_script_for_cancellation_support():
    with patch("agents.executor.supabase") as mock_supabase, \
         patch("agents.executor.log_event"), \
         patch("agents.executor.execute_script") as mock_execute:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_execute.return_value = ("", "", 0)

        executor(base_state())

    mock_execute.assert_called_once_with("print(42)", "test-123")
