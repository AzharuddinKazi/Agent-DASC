import json
from unittest.mock import patch, MagicMock
from agents.question_generator import question_generator


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 20,
        "duration_ms":   800,
        "agent":         "question_generator",
        "tier":          "medium",
    }


def base_state():
    return {
        "task_id":          "test-123",
        "query":            "How is fraud risk distributed across entities?",
        "domain_pack_id":   None,
        "data_descriptions": {"test.csv": "CSV with columns: entity, amount, is_fraud"},
    }


def hypothesis_json():
    return json.dumps([
        {"hypothesis": "Fraud is concentrated in a few entities.", "question": "Fraud rate by entity, ranked."},
        {"hypothesis": "High-fraud entities share a common channel.", "question": "Channel mix for the top-5 fraud entities."},
    ])


def test_parses_hypothesis_question_pairs():
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.return_value = make_mock_llm_result(hypothesis_json())

        result = question_generator(base_state())

    assert result["sub_questions"] == [
        "Fraud rate by entity, ranked.",
        "Channel mix for the top-5 fraud entities.",
    ]
    assert result["hypotheses"] == {
        "Fraud rate by entity, ranked.": "Fraud is concentrated in a few entities.",
        "Channel mix for the top-5 fraud entities.": "High-fraud entities share a common channel.",
    }
    assert result["current_sub_idx"] == 0
    assert result["sub_results"] == {}
    assert result["sub_question_rounds"] == {
        "Fraud rate by entity, ranked.": 0,
        "Channel mix for the top-5 fraud entities.": 0,
    }


def test_dedupes_by_question_text_preserving_order():
    dup_json = json.dumps([
        {"hypothesis": "H1", "question": "Same question?"},
        {"hypothesis": "H2", "question": "Different question?"},
        {"hypothesis": "H1 again", "question": "Same question?"},
    ])
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.return_value = make_mock_llm_result(dup_json)

        result = question_generator(base_state())

    assert result["sub_questions"] == ["Same question?", "Different question?"]
    assert result["hypotheses"]["Same question?"] == "H1"


def test_tolerates_plain_string_array_from_model():
    """Model ignores the requested {hypothesis, question} shape and returns bare strings —
    degrade gracefully (question with no hypothesis), don't crash."""
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.return_value = make_mock_llm_result(json.dumps(["Plain question?"]))

        result = question_generator(base_state())

    assert result["sub_questions"] == ["Plain question?"]
    assert result["hypotheses"] == {}


def test_retries_once_on_malformed_json_and_uses_the_good_retry():
    """Simulates a truncated/garbled model response (observed in practice: JSON array cut
    off mid-object) followed by a clean retry — the clean retry should win."""
    garbled = '[{"hypothesis":"H1","question":"Q1?"},{"hypothesis":"H2","quest'
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.side_effect = [
            make_mock_llm_result(garbled),
            make_mock_llm_result(hypothesis_json()),
        ]

        result = question_generator(base_state())

    assert mock_router.complete.call_count == 2
    assert result["sub_questions"] == [
        "Fraud rate by entity, ranked.",
        "Channel mix for the top-5 fraud entities.",
    ]


def test_keeps_first_attempt_when_retry_is_also_malformed():
    """Both attempts garbled — don't crash, don't loop forever, just proceed with
    whatever the first attempt salvaged (evaluator/gap-loop can still recover downstream)."""
    garbled_1 = "not json and not a real question list at all " * 20
    garbled_2 = ""
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.side_effect = [
            make_mock_llm_result(garbled_1),
            make_mock_llm_result(garbled_2),
        ]

        result = question_generator(base_state())

    assert mock_router.complete.call_count == 2
    assert len(result["sub_questions"]) == 1


def test_non_json_fallback_degrades_without_crashing():
    with patch("agents.question_generator.supabase") as mock_supabase, \
         patch("agents.question_generator.log_event"), \
         patch("agents.question_generator.router") as mock_router, \
         patch("agents.question_generator.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_pack.return_value = {"subquestion_dimensions": []}
        mock_router.complete.return_value = make_mock_llm_result(
            "1. First question?\n2. Second question?"
        )

        result = question_generator(base_state())

    assert result["sub_questions"] == ["First question?", "Second question?"]
    assert result["hypotheses"] == {}
