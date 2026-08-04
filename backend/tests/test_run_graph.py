import pytest
from unittest.mock import patch, MagicMock
import main
from agents.cancellation import TaskCancelled, TaskPaused, AwaitingReview


@pytest.mark.asyncio
async def test_run_graph_marks_task_stopped_on_task_cancelled():
    """Regression test for the Stop button: a cancelled task must land on status
    "stopped", not "failed" — a stop is an intentional user action, not an error, and the
    UI/telemetry treat those very differently (Sentry capture, "Analysis Failed" banner)."""
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.sentry_sdk") as mock_sentry, \
         patch("main.clear_cancellation") as mock_clear:
        mock_graph.invoke.side_effect = TaskCancelled("Task task-123 was stopped by the user")
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    update_kwargs = mock_supabase.table.return_value.update.call_args[0][0]
    assert update_kwargs["status"] == "stopped"
    mock_sentry.capture_exception.assert_not_called()  # not an error — no Sentry noise
    mock_clear.assert_called_once_with("task-123")


@pytest.mark.asyncio
async def test_run_graph_marks_task_paused_on_task_paused():
    """A pause is resumable, not an error — must not be reported as "failed" and must not
    overwrite final_result (nothing to persist; the checkpointer already has the state)."""
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.sentry_sdk") as mock_sentry, \
         patch("main.clear_cancellation") as mock_clear:
        mock_graph.invoke.side_effect = TaskPaused("Task task-123 was paused by the user")
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    update_kwargs = mock_supabase.table.return_value.update.call_args[0][0]
    assert update_kwargs == {"status": "paused"}
    mock_sentry.capture_exception.assert_not_called()
    mock_clear.assert_called_once_with("task-123")


@pytest.mark.asyncio
async def test_run_graph_marks_task_awaiting_review_on_awaiting_review():
    """human_review_gate's pause: not an error, not resumable via the plain Resume
    button — needs a decision via /review instead, so it gets its own distinct status."""
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.sentry_sdk") as mock_sentry, \
         patch("main.clear_cancellation") as mock_clear:
        mock_graph.invoke.side_effect = AwaitingReview("Task task-123 awaiting human review decision")
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    update_kwargs = mock_supabase.table.return_value.update.call_args[0][0]
    assert update_kwargs == {"status": "awaiting_review"}
    mock_sentry.capture_exception.assert_not_called()
    mock_clear.assert_called_once_with("task-123")


@pytest.mark.asyncio
async def test_run_graph_resume_invokes_graph_with_none_state_same_thread_id():
    """The actual resume mechanism: passing None (not a fresh initial_state) with the
    same thread_id is what makes LangGraph's checkpointer replay from the last completed
    node instead of starting the task over."""
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.clear_cancellation"):
        mock_graph.invoke.return_value = {"status": "completed", "final_result": "ok"}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", None)

    mock_graph.invoke.assert_called_once_with(None, config={"configurable": {"thread_id": "task-123"}})


@pytest.mark.asyncio
async def test_run_graph_marks_task_failed_on_other_exceptions():
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.logger"), \
         patch("main.sentry_sdk") as mock_sentry, \
         patch("main.clear_cancellation") as mock_clear:
        mock_graph.invoke.side_effect = RuntimeError("something broke")
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    update_kwargs = mock_supabase.table.return_value.update.call_args[0][0]
    assert update_kwargs["status"] == "failed"
    mock_sentry.capture_exception.assert_called_once()
    mock_clear.assert_called_once_with("task-123")


@pytest.mark.asyncio
async def test_run_graph_never_stores_the_raw_exception_message_on_infrastructure_failure():
    """Regression test: final_result on an unexpected infrastructure error (a bug in our
    own code, a DB error — not a generated script's own error) used to be str(e)
    verbatim, served directly through GET /api/v1/get_task. That could plausibly include
    connection strings or other internals depending on what actually broke. Full detail
    still reaches Sentry/logger.exception — just not the API response."""
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.logger"), \
         patch("main.sentry_sdk"), \
         patch("main.clear_cancellation"):
        mock_graph.invoke.side_effect = RuntimeError("postgresql://user:hunter2@internal-host/db unreachable")
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    update_kwargs = mock_supabase.table.return_value.update.call_args[0][0]
    assert "hunter2" not in update_kwargs["final_result"]
    assert "postgresql://" not in update_kwargs["final_result"]
    assert update_kwargs["final_result"] == main.GENERIC_INFRASTRUCTURE_ERROR


@pytest.mark.asyncio
async def test_run_graph_clears_cancellation_flag_on_success():
    with patch.object(main, "graph") as mock_graph, \
         patch("main.supabase") as mock_supabase, \
         patch("main.log_event"), \
         patch("main.clear_cancellation") as mock_clear:
        mock_graph.invoke.return_value = {"status": "completed", "final_result": "ok"}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await main.run_graph("task-123", {"task_id": "task-123"})

    mock_clear.assert_called_once_with("task-123")
