from unittest.mock import patch, MagicMock
from llm_router import LLMRouter, get_speed_profile, get_model_override


def make_mock_response(text="test response", model="openai/gpt-oss-20b:free",
                        input_tokens=10, output_tokens=5, status_code=200, finish_reason="stop"):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = text
    mock.json.return_value = {
        "choices": [{"message": {"content": text}, "finish_reason": finish_reason}],
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


def test_fast_paid_high_medium_and_coder_are_paid_but_low_stays_free():
    """low (analyzer, sub_result_collector) isn't the speed bottleneck this profile
    exists to test, so it deliberately reuses the free profile's low model rather than
    paying for it too — high/medium/coder are the actual "fast_paid" part."""
    assert set(LLMRouter._FAST_PAID_MODELS) == {"high", "medium", "low", "coder"}
    assert not LLMRouter._FAST_PAID_MODELS["high"].endswith(":free")
    assert not LLMRouter._FAST_PAID_MODELS["medium"].endswith(":free")
    assert not LLMRouter._FAST_PAID_MODELS["coder"].endswith(":free")
    assert LLMRouter._FAST_PAID_MODELS["low"] == LLMRouter._FREE_MODELS["low"]


def test_code_agents_use_the_coder_pseudo_tier_not_their_nominal_tier():
    """coder/debugger/finalizer all generate and execute real Python (see
    llm_router.py's _CODE_AGENTS comment) — they should draw from the "coder" key in
    both profiles' model dicts, not their AGENT_TIERS entry (finalizer is nominally
    "medium", but that's about output-formatting agents in general, not this one)."""
    router = LLMRouter.__new__(LLMRouter)
    for agent in ("coder", "debugger", "finalizer"):
        assert agent in router._CODE_AGENTS
    assert "coder" in LLMRouter._FREE_MODELS
    assert "coder" in LLMRouter._FAST_PAID_MODELS


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


def test_get_model_override_returns_none_when_no_row_exists():
    with patch("db.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        assert get_model_override("planner") is None


def test_get_model_override_returns_the_stored_model_id():
    with patch("db.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"model_id": "dsstar-high:16k"}]
        )
        assert get_model_override("planner") == "dsstar-high:16k"


def test_get_model_override_fails_closed_to_none_on_db_error():
    with patch("db.supabase") as mock_sb:
        mock_sb.table.side_effect = RuntimeError("db down")
        assert get_model_override("planner") is None


def test_complete_prefers_db_model_override_over_tier_default():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("llm_router.get_model_override", return_value="admin-picked-model"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["model"] == "admin-picked-model"


def test_complete_uses_fast_paid_models_when_that_profile_is_active():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="fast_paid"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, call_kwargs = mock_post.call_args
        assert call_kwargs["json"]["model"] == LLMRouter._FAST_PAID_MODELS["high"]


def test_complete_routes_code_agents_to_the_coder_pseudo_tier():
    """coder/debugger/finalizer all get the "coder" model, not their AGENT_TIERS entry
    (finalizer is nominally "medium") — see llm_router.py's _CODE_AGENTS."""
    for agent in ("coder", "debugger", "finalizer"):
        with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
             patch("llm_router.get_speed_profile", return_value="free"), \
             patch("requests.Session.post") as mock_post:
            mock_post.return_value = make_mock_response()

            router = LLMRouter()
            result = router.complete(agent=agent, prompt="Test")

            _, call_kwargs = mock_post.call_args
            assert call_kwargs["json"]["model"] == LLMRouter._FREE_MODELS["coder"]
            assert result["tier"] == "coder"


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


def test_complete_sends_an_explicit_max_tokens():
    """Regression test: a real report was observed truncated mid-sentence with no
    closing JSON braces at all (see TASKS.md, 2026-08-23) — no max_tokens was ever
    sent, so every call rode on the provider's own unstated default completion cap."""
    import llm_router as llm_router_module

    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response()

        router = LLMRouter()
        router.complete(agent="planner", prompt="Test")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["max_tokens"] == llm_router_module.LLM_MAX_TOKENS


def test_complete_logs_a_task_event_when_the_completion_is_truncated():
    """A response cut off at the max_tokens ceiling (finish_reason "length") isn't
    retried (a repeat attempt would likely hit the same ceiling) but must be visible —
    previously a truncated completion surfaced only as a bare downstream JSON-parse
    failure with no indication of why."""
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("llm_router.log_event") as mock_log_event, \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response(finish_reason="length")

        router = LLMRouter()
        result = router.complete(agent="writer", prompt="Test", task_id="task-123")

    # Still returns the (truncated) text rather than raising — the caller's own JSON
    # parsing is what actually fails on genuinely incomplete output, same as before.
    assert result["text"] == "test response"
    messages = [c.args[2] for c in mock_log_event.call_args_list]
    assert any("token limit" in m for m in messages)


def test_complete_does_not_log_a_truncation_event_on_a_normal_completion():
    with patch("llm_router.OPENROUTER_API_KEY", "dummy-key"), \
         patch("llm_router.get_speed_profile", return_value="free"), \
         patch("llm_router.log_event") as mock_log_event, \
         patch("requests.Session.post") as mock_post:
        mock_post.return_value = make_mock_response(finish_reason="stop")

        router = LLMRouter()
        router.complete(agent="writer", prompt="Test", task_id="task-123")

    messages = [c.args[2] for c in mock_log_event.call_args_list]
    assert not any("token limit" in m for m in messages)


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
