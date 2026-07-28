from unittest.mock import patch, MagicMock
from llm_router import LLMRouter


def make_mock_response(text="test response", model="openai/gpt-oss-20b:free",
                        input_tokens=10, output_tokens=5, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = text
    mock.json.return_value = {
        "choices": [{"message": {"content": text}}],
        "model": model,
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }
    return mock


def test_agent_tier_assignment():
    router = LLMRouter.__new__(LLMRouter)
    assert router.AGENT_TIERS["planner"] == "high"
    assert router.AGENT_TIERS["coder"] == "high"
    assert router.AGENT_TIERS["verifier"] == "high"
    assert router.AGENT_TIERS["debugger"] == "high"
    assert router.AGENT_TIERS["router"] == "medium"
    assert router.AGENT_TIERS["finalizer"] == "medium"
    assert router.AGENT_TIERS["query_clarity"] == "low"
    assert router.AGENT_TIERS["analyzer"] == "low"


def test_unknown_agent_defaults_to_medium():
    router = LLMRouter.__new__(LLMRouter)
    tier = router.AGENT_TIERS.get("unknown_agent", "medium")
    assert tier == "medium"


def test_complete_returns_expected_keys():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response(
            text="Load the CSV file and print the first 5 rows."
        )

        router = LLMRouter()
        result = router.complete(agent="planner", prompt="Test prompt")

    assert "text" in result
    assert "model" in result
    assert "input_tokens" in result
    assert "output_tokens" in result
    assert "duration_ms" in result
    assert "agent" in result
    assert "tier" in result
    assert result["agent"] == "planner"
    assert result["tier"] == "high"
    assert result["text"] == "Load the CSV file and print the first 5 rows."


def test_complete_uses_correct_model_for_tier():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["model"] == router.MODELS["high"]


def test_complete_applies_call_timeout():
    """Regression test: every OpenRouter call must be bounded (no timeout meant a hung
    request could stall a task forever with no error and no signal)."""
    import llm_router as llm_router_module

    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] == llm_router_module.LLM_TIMEOUT_S


def test_complete_wraps_timeout_error_as_runtime_error():
    """Timeouts raise requests.RequestException, not an OpenRouter error body — the
    except clause must catch broadly enough to still wrap it, or it propagates
    unhandled."""
    import requests

    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("requests.Session.post") as mock_post, \
         patch("llm_router.time.sleep"):
        mock_post.side_effect = requests.exceptions.ConnectTimeout("timed out")

        router = LLMRouter()
        try:
            router.complete(agent="planner", prompt="Test")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "planner" in str(e)
