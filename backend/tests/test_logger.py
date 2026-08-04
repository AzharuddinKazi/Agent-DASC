from unittest.mock import patch, MagicMock
from agents.logger import log_event


def test_log_event_appends_via_atomic_rpc():
    with patch("agents.logger.supabase") as mock_sb:
        mock_sb.rpc.return_value.execute.return_value = MagicMock()

        log_event("task-1", "coder", "Script generated", "success", {"round": 1})

        call_args = mock_sb.rpc.call_args
    assert call_args.args[0] == "append_task_log"
    payload = call_args.args[1]
    assert payload["p_task_id"] == "task-1"
    entry = payload["p_entry"]
    assert entry["agent"] == "coder"
    assert entry["message"] == "Script generated"
    assert entry["status"] == "success"
    assert entry["round"] == 1
    assert "ts" in entry


def test_log_event_falls_back_to_read_modify_write_when_rpc_fails():
    """The RPC (migrations/2026-08-03_atomic_log_append.sql) may not exist yet in an
    environment that hasn't applied the migration — must degrade to the old behavior
    instead of losing the entry outright."""
    with patch("agents.logger.supabase") as mock_sb:
        mock_sb.rpc.side_effect = Exception("function append_task_log does not exist")
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"logs": [{"agent": "analyzer", "message": "existing"}]}]
        )
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        log_event("task-1", "coder", "Script generated", "success")

        update_call = mock_sb.table.return_value.update.call_args[0][0]
    assert len(update_call["logs"]) == 2
    assert update_call["logs"][0]["message"] == "existing"
    assert update_call["logs"][1]["message"] == "Script generated"


def test_log_event_fallback_handles_missing_task_row():
    with patch("agents.logger.supabase") as mock_sb:
        mock_sb.rpc.side_effect = Exception("rpc unavailable")
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        log_event("task-1", "analyzer", "Scanning files", "running")

        update_call = mock_sb.table.return_value.update.call_args[0][0]
    assert len(update_call["logs"]) == 1
    assert update_call["logs"][0]["agent"] == "analyzer"
    assert update_call["logs"][0]["message"] == "Scanning files"
    assert update_call["logs"][0]["status"] == "running"


def test_log_event_never_raises_even_if_everything_fails():
    """Logging must never take the pipeline down with it."""
    with patch("agents.logger.supabase") as mock_sb:
        mock_sb.rpc.side_effect = Exception("rpc unavailable")
        mock_sb.table.side_effect = Exception("db unreachable")

        log_event("task-1", "coder", "Script generated", "success")  # must not raise
