import json
from unittest.mock import patch, MagicMock
from agents.query_clarity import generate_clarifying_questions, _parse_questions, _json_parse_failed


def make_mock_llm_result(text):
    return {
        "text":          text,
        "model":         "test-model",
        "input_tokens":  50,
        "output_tokens": 20,
        "duration_ms":   400,
        "agent":         "query_clarity",
        "tier":          "low",
    }


def questions_json():
    return json.dumps([
        {
            "question": "Which time period should 'recent' cover?",
            "header": "Timeframe",
            "options": [
                {"label": "Last 30 days", "description": "Most recent month of data"},
                {"label": "Last quarter", "description": "Last 3 months"},
            ],
        }
    ])


def test_parse_questions_returns_well_formed_list():
    parsed = _parse_questions(questions_json())
    assert len(parsed) == 1
    assert parsed[0]["question"] == "Which time period should 'recent' cover?"
    assert parsed[0]["header"] == "Timeframe"
    assert len(parsed[0]["options"]) == 2


def test_parse_questions_returns_empty_list_for_non_json():
    assert _parse_questions("not json at all") == []


def test_parse_questions_returns_empty_list_for_empty_string():
    assert _parse_questions("") == []


def test_parse_questions_strips_code_fences():
    fenced = f"```json\n{questions_json()}\n```"
    parsed = _parse_questions(fenced)
    assert len(parsed) == 1


def test_parse_questions_drops_entries_with_fewer_than_two_options():
    """A "clarifying question" with 0-1 concrete options isn't a real choice — drop it
    rather than showing the user a popup with nothing meaningful to pick."""
    raw = json.dumps([
        {"question": "Real question?", "header": "H", "options": [
            {"label": "A", "description": ""}, {"label": "B", "description": ""}
        ]},
        {"question": "Broken question?", "header": "H", "options": [{"label": "Only one", "description": ""}]},
        {"question": "No options at all?", "header": "H", "options": []},
    ])
    parsed = _parse_questions(raw)
    assert len(parsed) == 1
    assert parsed[0]["question"] == "Real question?"


def test_parse_questions_caps_questions_and_options():
    raw = json.dumps([
        {
            "question": f"Question {i}?",
            "header": "H",
            "options": [{"label": f"opt{j}", "description": ""} for j in range(10)],
        }
        for i in range(10)
    ])
    parsed = _parse_questions(raw)
    assert len(parsed) == 4  # MAX_QUESTIONS
    assert all(len(q["options"]) == 4 for q in parsed)  # MAX_OPTIONS_PER_QUESTION


def test_parse_questions_ignores_malformed_entries_without_crashing():
    raw = json.dumps(["a bare string", {"no_question_key": True}, None, 42])
    assert _parse_questions(raw) == []


def test_generate_clarifying_questions_returns_parsed_questions():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.return_value = make_mock_llm_result(questions_json())

        result = generate_clarifying_questions("How are recent sales trending?", "qa", None)

    assert len(result) == 1
    assert result[0]["header"] == "Timeframe"


def test_generate_clarifying_questions_returns_empty_list_when_unambiguous():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.return_value = make_mock_llm_result("[]")

        result = generate_clarifying_questions("What is the total row count in transactions.csv?", "qa", None)

    assert result == []


def test_json_parse_failed_true_for_malformed_output():
    """Regression test for the real observed failure: a smaller model wrapped each
    question in its own [...] instead of one flat array."""
    malformed = '[{"question": "Q1?"}], {"question": "Q2?"}, {"question": "Q3?"}()]'
    assert _json_parse_failed(malformed) is True


def test_json_parse_failed_false_for_empty_array():
    """An empty array is the model correctly deciding no clarification is needed —
    not a failure, and must not trigger a wasted retry."""
    assert _json_parse_failed("[]") is False
    assert _json_parse_failed("") is False


def test_json_parse_failed_false_for_valid_array():
    assert _json_parse_failed(questions_json()) is False


def test_generate_clarifying_questions_retries_once_on_malformed_output_and_uses_the_good_retry():
    malformed = '[{"question": "Q1?"}], {"question": "Q2?"}()]'
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.side_effect = [
            make_mock_llm_result(malformed),
            make_mock_llm_result(questions_json()),
        ]

        result = generate_clarifying_questions("How are recent sales trending?", "qa", None)

    assert mock_router.complete.call_count == 2
    assert len(result) == 1
    assert result[0]["header"] == "Timeframe"


def test_generate_clarifying_questions_does_not_retry_on_clean_empty_result():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.return_value = make_mock_llm_result("[]")

        generate_clarifying_questions("Row count?", "qa", None)

    assert mock_router.complete.call_count == 1


def test_generate_clarifying_questions_keeps_first_attempt_when_retry_also_malformed():
    malformed_1 = '[{"question": "Q1?"}], {"question": "Q2?"}()]'
    malformed_2 = "still not valid json"
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.side_effect = [
            make_mock_llm_result(malformed_1),
            make_mock_llm_result(malformed_2),
        ]

        result = generate_clarifying_questions("Some query", "qa", None)

    assert mock_router.complete.call_count == 2
    assert result == []  # both malformed — degrades to no clarification, doesn't crash


def test_generate_clarifying_questions_survives_llm_failure():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.side_effect = RuntimeError("OpenRouter down")

        result = generate_clarifying_questions("Some query", "qa", None)

    assert result == []


def test_generate_clarifying_questions_includes_report_mode_context_in_prompt():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.return_value = make_mock_llm_result("[]")

        generate_clarifying_questions("Investigate fraud patterns", "report", None)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "Investigative report" in prompt


def test_generate_clarifying_questions_falls_back_when_no_cached_data():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_router.complete.return_value = make_mock_llm_result("[]")

        generate_clarifying_questions("Some query", "qa", None)

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "No data has been profiled yet" in prompt


def test_generate_clarifying_questions_includes_domain_persona_when_pack_active():
    with patch("agents.query_clarity.router") as mock_router, \
         patch("agents.query_clarity.supabase") as mock_supabase, \
         patch("agents.query_clarity.get_active_pack_config") as mock_pack:
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        mock_pack.return_value = {"report_persona": "You are a Medicare program-integrity analyst."}
        mock_router.complete.return_value = make_mock_llm_result("[]")

        generate_clarifying_questions("Some query", "qa", "medicare-claims")

        prompt = mock_router.complete.call_args.kwargs["prompt"]

    assert "You are a Medicare program-integrity analyst." in prompt
