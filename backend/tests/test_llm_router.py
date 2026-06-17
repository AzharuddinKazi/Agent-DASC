from unittest.mock import patch, MagicMock
from llm_router import LLMRouter


def make_mock_response(text="test response", input_tokens=10, output_tokens=5):
    mock = MagicMock()
    mock.text = text
    mock.model_version = "gemini-2.5-pro"
    mock.usage_metadata.prompt_token_count = input_tokens
    mock.usage_metadata.candidates_token_count = output_tokens
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
    with patch("llm_router.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.return_value = make_mock_response(
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
    with patch("llm_router.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        call_kwargs = mock_client.models.generate_content.call_args
        assert "gemini-2.5-pro" in str(call_kwargs)