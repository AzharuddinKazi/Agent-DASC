from unittest.mock import patch, MagicMock
from agents.graph import gap_question_generator


def base_state(**overrides):
    state = {
        "task_id":       "test-123",
        "report_gaps":   [{"question": "What drives the top entity's fraud rate", "hypothesis": "A single channel."}],
        "sub_questions": ["Fraud rate by entity?"],
        "hypotheses":    {"Fraud rate by entity?": "Fraud is concentrated in a few entities."},
    }
    state.update(overrides)
    return state


def test_appends_gap_question_and_hypothesis():
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = gap_question_generator(base_state())

    assert result["sub_questions"] == [
        "Fraud rate by entity?",
        "What drives the top entity's fraud rate?",
    ]
    assert result["hypotheses"] == {
        "Fraud rate by entity?": "Fraud is concentrated in a few entities.",
        "What drives the top entity's fraud rate?": "A single channel.",
    }


def test_appends_question_mark_only_if_missing():
    state = base_state(report_gaps=[{"question": "Already has one?", "hypothesis": ""}])
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = gap_question_generator(state)

    assert result["sub_questions"][-1] == "Already has one?"


def test_gap_with_no_hypothesis_does_not_add_empty_entry():
    state = base_state(report_gaps=[{"question": "No hypothesis here", "hypothesis": ""}])
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = gap_question_generator(state)

    assert "No hypothesis here?" not in result["hypotheses"]


def test_resets_qa_pipeline_state():
    with patch("db.supabase") as mock_supabase, \
         patch("agents.graph.log_event"):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = gap_question_generator(base_state())

    assert result["cumulative_plan"] == []
    assert result["current_round"] == 0
    assert result["final_result"] is None
