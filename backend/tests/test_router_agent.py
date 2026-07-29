from unittest.mock import patch, MagicMock
from agents.router_agent import router_agent


def make_mock_llm_result(text="Add Step"):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 5,
        "duration_ms":   500,
        "agent":         "router",
        "tier":          "medium",
    }


def base_state():
    return {
        "task_id":          "test-123",
        "query":            "Top-level research query",
        "data_descriptions": {"test.csv": "CSV with columns: amount, currency"},
        "cumulative_plan":  ["Load the CSV."],
        "execution_result": "insufficient result",
    }


def test_router_agent_decides_against_current_sub_question_not_top_level_query():
    """Regression test: router_agent used to always prompt with state["query"], so its
    backtrack/add-step decision was made against the wrong question in report mode."""
    with patch("agents.router_agent.supabase") as mock_supabase, \
         patch("agents.router_agent.log_event"), \
         patch("agents.router_agent.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result()

        state = base_state()
        state["sub_questions"] = ["First sub-question?", "Second sub-question?"]
        state["current_sub_idx"] = 1

        router_agent(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Second sub-question?" in prompt
    assert "First sub-question?" not in prompt
    assert "Top-level research query" not in prompt


def test_router_agent_falls_back_to_query_in_qa_mode():
    with patch("agents.router_agent.supabase") as mock_supabase, \
         patch("agents.router_agent.log_event"), \
         patch("agents.router_agent.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result()

        router_agent(base_state())

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Top-level research query" in prompt


def test_router_agent_empty_response_defaults_to_add_step():
    with patch("agents.router_agent.supabase") as mock_supabase, \
         patch("agents.router_agent.log_event"), \
         patch("agents.router_agent.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("")

        result = router_agent(base_state())

    assert result == {"router_decision": "add_step"}


def test_router_agent_step_response_with_no_number_defaults_to_add_step():
    """"Step" alone (no number) must not crash on `decision.split()[1]`."""
    with patch("agents.router_agent.supabase") as mock_supabase, \
         patch("agents.router_agent.log_event"), \
         patch("agents.router_agent.router") as mock_router:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_router.complete.return_value = make_mock_llm_result("Step")

        result = router_agent(base_state())

    assert result == {"router_decision": "add_step"}
