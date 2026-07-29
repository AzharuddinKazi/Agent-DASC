import pytest
from unittest.mock import patch, MagicMock
from agents.coder import coder


@pytest.fixture(autouse=True)
def mock_live_dependencies():
    with patch("agents.coder.supabase") as mock_supabase, \
         patch("agents.coder.log_event"), \
         patch("agents.coder.retrieve_grounded_knowledge", return_value="") as mock_dk:
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        yield mock_dk


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 20,
        "duration_ms":   800,
        "agent":         "coder",
        "tier":          "high",
    }


def base_state():
    return {
        "task_id":          "test-123",
        "data_descriptions": {"test.csv": "CSV with columns: amount, currency"},
        "cumulative_plan":  ["Load the CSV and print its shape."],
        "current_script":   "",
        "current_round":    0,
    }


def test_coder_round_0_uses_init_prompt_and_strips_code_fence():
    with patch("agents.coder.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result(
            "```python\nimport pandas as pd\nprint(pd.read_csv('/workspace/data/test.csv').shape)\n```"
        )
        result = coder(base_state())

    assert result["current_script"] == "import pandas as pd\nprint(pd.read_csv('/workspace/data/test.csv').shape)"


def test_coder_strips_fence_even_when_closing_fence_is_missing():
    """Regression test: the model's response can get cut off mid-completion, leaving no
    closing ``` — the old line-based stripper (`split("\\n")[1:-1]`) silently dropped the
    last real line of code in that case instead of just leaving it in."""
    with patch("agents.coder.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result(
            "```python\nimport pandas as pd\nprint(pd.read_csv('/workspace/data/test.csv').shape)"
        )
        result = coder(base_state())

    assert result["current_script"] == (
        "import pandas as pd\nprint(pd.read_csv('/workspace/data/test.csv').shape)"
    )


def test_coder_round_1_uses_next_prompt_and_builds_on_base_code():
    with patch("agents.coder.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result(
            "```python\nprint(df.groupby('currency').amount.sum())\n```"
        )
        state = base_state()
        state["current_round"] = 1
        state["current_script"] = "import pandas as pd\ndf = pd.read_csv('/workspace/data/test.csv')"
        state["cumulative_plan"] = [
            "Load the CSV and print its shape.",
            "Group by currency and sum amounts.",
        ]

        result = coder(state)
        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "df = pd.read_csv" in prompt
    assert "Group by currency and sum amounts." in prompt
    assert result["current_script"] == "print(df.groupby('currency').amount.sum())"


def test_coder_retrieves_domain_knowledge_grounded_on_current_plan_step_and_injects_it(mock_live_dependencies):
    mock_dk = mock_live_dependencies
    mock_dk.return_value = "# Domain knowledge\nSP_CHF: 1=Yes, 2=No"
    with patch("agents.coder.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result("```python\nprint(1)\n```")
        state = base_state()
        state["cumulative_plan"] = ["Sum the SP_CHF flag for each beneficiary."]

        coder(state)

        prompt = mock_router.complete.call_args.kwargs["prompt"]
        retrieval_text = mock_dk.call_args[0][0]

    assert retrieval_text == "Sum the SP_CHF flag for each beneficiary."
    assert "SP_CHF: 1=Yes, 2=No" in prompt


def test_coder_returns_only_current_script_key():
    with patch("agents.coder.router") as mock_router:
        mock_router.complete.return_value = make_mock_llm_result("print(1)")
        result = coder(base_state())

    assert set(result.keys()) == {"current_script"}
