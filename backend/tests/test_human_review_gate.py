import pytest
from unittest.mock import patch, MagicMock
from agents.graph import human_review_gate
from agents.cancellation import AwaitingReview


def base_state(**overrides):
    state = {
        "task_id":       "test-123",
        "report_verdict": "insufficient",
        "report_gaps":   [{"question": "What drives the top entity's fraud rate", "hypothesis": "A single channel."}],
        "report_rounds": 1,
    }
    state.update(overrides)
    return state


def test_raises_awaiting_review_when_no_decision_recorded():
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event") as mock_log_event, \
         patch("agents.graph.get_review_decision", return_value=None):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with pytest.raises(AwaitingReview):
            human_review_gate(base_state())

    # The reviewer needs the evaluator's verdict/gaps surfaced to make a decision.
    args, kwargs = mock_log_event.call_args
    assert args[1] == "human_review_gate"
    meta = args[4] if len(args) > 4 else kwargs.get("meta")
    assert meta["verdict"] == "insufficient"
    assert meta["gaps"] == [{"question": "What drives the top entity's fraud rate", "hypothesis": "A single channel."}]
    assert meta["round"] == 1


def test_returns_decision_when_already_recorded():
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"), \
         patch("agents.graph.get_review_decision", return_value="refine"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = human_review_gate(base_state())

    assert result == {"human_review_decision": "refine"}


def test_returns_finalize_decision_when_recorded():
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"), \
         patch("agents.graph.get_review_decision", return_value="finalize"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = human_review_gate(base_state())

    assert result == {"human_review_decision": "finalize"}
