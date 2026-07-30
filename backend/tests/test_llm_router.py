from unittest.mock import patch, MagicMock
from llm_router import LLMRouter, get_speed_profile


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
    assert router.AGENT_TIERS["query_clarity"] == "medium"
    assert router.AGENT_TIERS["analyzer"] == "low"


def test_unknown_agent_defaults_to_medium():
    router = LLMRouter.__new__(LLMRouter)
    tier = router.AGENT_TIERS.get("unknown_agent", "medium")
    assert tier == "medium"


def test_free_models_require_no_billing():
    """Every normal dev/CI run must be able to use free models with zero billing
    setup — this is the safety property the "free" profile protects."""
    assert all(model_id.endswith(":free") for model_id in LLMRouter._FREE_MODELS.values())


def test_fast_paid_high_and_medium_are_paid_but_low_stays_free():
    """low (analyzer, sub_result_collector) isn't the speed bottleneck this profile
    exists to test, so it deliberately reuses the free profile's low model rather than
    paying for it too — high and medium are the actual "fast_paid" part."""
    assert set(LLMRouter._FAST_PAID_MODELS) == {"high", "medium", "low"}
    assert not LLMRouter._FAST_PAID_MODELS["high"].endswith(":free")
    assert not LLMRouter._FAST_PAID_MODELS["medium"].endswith(":free")
    assert LLMRouter._FAST_PAID_MODELS["low"] == LLMRouter._FREE_MODELS["low"]


def test_models_for_profile_selects_the_matching_dict():
    """The dict swap that makes toggling the profile actually change every tier at
    once, not just one."""
    assert LLMRouter.models_for_profile("free") == LLMRouter._FREE_MODELS
    assert LLMRouter.models_for_profile("fast_paid") == LLMRouter._FAST_PAID_MODELS
    assert LLMRouter.models_for_profile("garbage") == LLMRouter._FREE_MODELS  # fail closed


def test_get_speed_profile_defaults_to_free_with_no_app_settings_row():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("db.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert get_speed_profile() == "free"


def test_get_speed_profile_reads_the_live_app_settings_row():
    mock_result = MagicMock()
    mock_result.data = [{"value": "fast_paid"}]
    with patch("db.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert get_speed_profile() == "fast_paid"


def test_get_speed_profile_fails_closed_to_free_when_db_is_unreachable():
    with patch("db.supabase") as mock_sb:
        mock_sb.table.side_effect = Exception("connection refused")
        assert get_speed_profile() == "free"


def test_get_speed_profile_fails_closed_to_free_on_an_invalid_stored_value():
    """Defensive against a bad manual DB edit — must never silently fall through to
    billed models on garbage input."""
    mock_result = MagicMock()
    mock_result.data = [{"value": "definitely-not-a-real-profile"}]
    with patch("db.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        assert get_speed_profile() == "free"


def test_complete_returns_expected_keys():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
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
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["model"] == LLMRouter._FREE_MODELS["high"]


def test_complete_uses_fast_paid_models_when_that_profile_is_active():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="fast_paid"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["model"] == LLMRouter._FAST_PAID_MODELS["high"]


def test_complete_applies_call_timeout():
    """Regression test: every OpenRouter call must be bounded (no timeout meant a hung
    request could stall a task forever with no error and no signal)."""
    import llm_router as llm_router_module

    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
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
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("requests.Session.post") as mock_post, \
         patch("llm_router.time.sleep"):
        mock_post.side_effect = requests.exceptions.ConnectTimeout("timed out")

        router = LLMRouter()
        try:
            router.complete(agent="planner", prompt="Test")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "planner" in str(e)
