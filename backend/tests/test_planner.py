import pytest
from unittest.mock import patch, MagicMock
from agents.planner import planner


@pytest.fixture(autouse=True)
def mock_live_dependencies():
    """planner() writes task progress to Supabase and retrieves domain-pack knowledge
    (Supabase + Gemini) on every call — mock both so these tests never hit live
    infrastructure. Without this, task_id="test-123" fails Postgres UUID validation
    against the real tasks table (the pre-existing failure these tests used to have).
    """
    with patch("agents.planner.supabase") as mock_supabase, \
         patch("agents.planner._domain_knowledge_section", return_value=""):
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        yield


def make_mock_llm_result(text="Load the transactions CSV file."):
    return {
        "text":          text,
        "model":         "gemini-2.5-pro",
        "input_tokens":  50,
        "output_tokens": 10,
        "duration_ms":   1200,
        "agent":         "planner",
        "tier":          "high",
    }


def base_state():
    return {
        "task_id":               "test-123",
        "query":                 "What is the total transaction volume by currency?",
        "formatting_guidelines": "Return a table",
        "data_descriptions":     {"test.csv": "CSV with columns: lfi_id, amount, currency"},
        "cumulative_plan":       [],
        "current_script":        "",
        "execution_result":      "",
        "exit_code":             0,
        "current_round":         0,
        "max_rounds":            20,
        "verifier_verdict":      "",
        "router_decision":       "",
        "status":                "queued",
        "final_result":          None,
    }


def test_planner_round_0_uses_init_prompt():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result(
            "Load transactions.csv and inspect the data."
        )
        state = base_state()
        result = planner(state)

    assert "cumulative_plan" in result
    assert len(result["cumulative_plan"]) == 1
    assert result["current_round"] == 1
    assert result["status"] == "running"


def test_planner_round_1_uses_next_prompt():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result(
            "Group by currency and sum the amounts."
        )
        state = base_state()
        state["current_round"] = 1
        state["cumulative_plan"] = ["Load transactions.csv and inspect the data."]
        state["execution_result"] = "lfi_id  amount  currency\nADCB    5000    AED"

        result = planner(state)

    assert len(result["cumulative_plan"]) == 2
    assert result["current_round"] == 2


def test_planner_appends_to_existing_plan():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result("Step 3 action")
        state = base_state()
        state["current_round"] = 2
        state["cumulative_plan"] = ["Step 1 action", "Step 2 action"]
        state["execution_result"] = "some result"

        result = planner(state)

    assert result["cumulative_plan"] == ["Step 1 action", "Step 2 action", "Step 3 action"]


def test_planner_returns_only_delta_keys():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result()
        result = planner(base_state())

    assert set(result.keys()) == {"cumulative_plan", "current_round", "status"}


def test_planner_uses_current_sub_question_not_top_level_query():
    """Regression test: planner used to always prompt with state["query"] (the top-level
    query) regardless of which sub-question it was working on — every sub-question's mini-
    pipeline received an identical prompt. It must now use the sub-question at
    current_sub_idx."""
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result()
        state = base_state()
        state["query"] = "Top-level research query"
        state["sub_questions"] = ["First sub-question?", "Second sub-question?"]
        state["current_sub_idx"] = 1

        planner(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Second sub-question?" in prompt
    assert "First sub-question?" not in prompt


def test_planner_injects_hypothesis_when_present():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result()
        state = base_state()
        state["sub_questions"] = ["Is fraud concentrated in one channel?"]
        state["current_sub_idx"] = 0
        state["hypotheses"] = {
            "Is fraud concentrated in one channel?": "Fraud is concentrated in the Online channel."
        }

        planner(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Fraud is concentrated in the Online channel." in prompt


def test_planner_omits_hypothesis_section_when_none_recorded():
    with patch("agents.planner.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result()
        result_prompt_state = base_state()

        planner(result_prompt_state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Hypothesis under test" not in prompt
