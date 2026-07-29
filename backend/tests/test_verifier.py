from unittest.mock import patch, MagicMock
from agents.verifier import verifier


def make_mock_llm_result(text="Yes"):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 5,
        "duration_ms":   500,
        "agent":         "verifier",
        "tier":          "high",
    }


def base_state():
    return {
        "task_id":          "test-123",
        "query":            "Top-level research query",
        "data_descriptions": {"test.csv": "CSV with columns: amount, currency"},
        "cumulative_plan":  ["Load the CSV."],
        "current_script":   "print('42')",
        "execution_result": "42",
        "current_round":    1,
    }


def test_verifier_checks_against_current_sub_question_not_top_level_query():
    """Regression test: verifier used to always prompt with state["query"], so it judged
    sufficiency against the wrong question in report mode — this made the 'bias toward
    Yes' instruction even more likely to rubber-stamp an off-target result."""
    with patch("agents.verifier.supabase") as mock_supabase, \
         patch("agents.verifier.log_event"), \
         patch("agents.verifier.retrieve_grounded_knowledge", return_value=""), \
         patch("agents.verifier.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result()

        state = base_state()
        state["sub_questions"] = ["First sub-question?", "Second sub-question?"]
        state["current_sub_idx"] = 1

        verifier(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Second sub-question?" in prompt
    assert "First sub-question?" not in prompt
    assert "Top-level research query" not in prompt


def test_verifier_falls_back_to_query_in_qa_mode():
    with patch("agents.verifier.supabase") as mock_supabase, \
         patch("agents.verifier.log_event"), \
         patch("agents.verifier.retrieve_grounded_knowledge", return_value=""), \
         patch("agents.verifier.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result()

        verifier(base_state())

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Top-level research query" in prompt


def test_verifier_grounds_retrieval_on_step_and_code_and_injects_it_into_prompt():
    """Regression test for the silent sign-inversion bug: the verifier previously had no
    domain knowledge at all, so it had no way to notice a miscoded/un-recoded column being
    summed as if it were already a clean count."""
    with patch("agents.verifier.supabase") as mock_supabase, \
         patch("agents.verifier.log_event"), \
         patch("agents.verifier.retrieve_grounded_knowledge") as mock_dk, \
         patch("agents.verifier.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_dk.return_value = "# Domain knowledge\nSP_CHF: 1=Yes, 2=No"
        mock_router.complete.return_value = make_mock_llm_result()

        state = base_state()
        state["current_script"] = "print(df[['SP_CHF']].sum())"

        verifier(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]
        retrieval_text = mock_dk.call_args[0][0]

    assert "print(df[['SP_CHF']].sum())" in retrieval_text
    assert "SP_CHF: 1=Yes, 2=No" in prompt


def test_verifier_empty_response_is_treated_as_insufficient():
    with patch("agents.verifier.supabase") as mock_supabase, \
         patch("agents.verifier.log_event"), \
         patch("agents.verifier.retrieve_grounded_knowledge", return_value=""), \
         patch("agents.verifier.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("")

        result = verifier(base_state())

    assert result == {"verifier_verdict": "insufficient"}
