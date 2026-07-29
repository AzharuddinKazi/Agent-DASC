from unittest.mock import patch
from agents.domain_knowledge import (
    _extract_column_tokens,
    _reciprocal_rank_fusion,
    retrieve_grounded_knowledge,
)


def test_extract_column_tokens_finds_upper_snake_case_identifiers():
    text = "Sum SP_CHF and SP_ALZHDMTA, then join on BENE_BIRTH_DT and PRVDR_NUM."
    assert _extract_column_tokens(text) == ["SP_CHF", "SP_ALZHDMTA", "BENE_BIRTH_DT", "PRVDR_NUM"]


def test_extract_column_tokens_expands_wildcard_prefix_against_real_columns():
    """Regression test for the actual bug this module exists to catch: the question that
    triggered the sign-inversion never named SP_CHF literally, only "sum of SP_* flags" —
    which isn't a real column and retrieves nothing on its own. Expanding it against the
    Analyzer's real column list is what makes the fix actually fire for that question."""
    text = "What is the count of chronic conditions (sum of SP_* flags) per beneficiary?"
    data_descriptions = {
        "beneficiary.csv": "SP_ALZHDMTA: int64\nSP_CHF: int64\nSP_CHRNKIDN: int64\nSP_CNCR: int64\nBENE_BIRTH_DT: int64"
    }
    tokens = _extract_column_tokens(text, data_descriptions)
    assert "SP_ALZHDMTA" in tokens
    assert "SP_CHF" in tokens
    assert "SP_CHRNKIDN" in tokens


def test_extract_column_tokens_wildcard_expansion_takes_priority_over_literal_mentions():
    """The literal columns in this question (MEDREIMB_IP, MEDREIMB_OP, MEDREIMB_CAR,
    BENE_BIRTH_DT) alone would fill the whole query budget before "SP_*" ever got
    expanded — exactly what happened with the real question that missed the bug. Wildcard
    expansions must win the budget over individually-named columns."""
    text = ("regression coefficient for count of chronic conditions (sum of SP_* flags) "
            "predicting MEDREIMB_IP+MEDREIMB_OP+MEDREIMB_CAR, adjusting for BENE_BIRTH_DT")
    data_descriptions = {"beneficiary.csv": "SP_ALZHDMTA: int64\nSP_CHF: int64\nSP_CHRNKIDN: int64"}
    tokens = _extract_column_tokens(text, data_descriptions)
    assert "SP_CHF" in tokens
    assert "SP_ALZHDMTA" in tokens


def test_extract_column_tokens_ignores_wildcard_prefix_with_no_matching_columns():
    text = "sum of ZZZ_* flags"
    tokens = _extract_column_tokens(text, {"f.csv": "SP_CHF: int64"})
    assert tokens == []


def test_extract_column_tokens_ignores_bare_acronyms_and_dedupes():
    text = "The USA CMS data has SP_CHF twice: SP_CHF and SP_CHF again, plus CLM_PMT_AMT."
    tokens = _extract_column_tokens(text)
    assert "USA" not in tokens
    assert "CMS" not in tokens
    assert tokens.count("SP_CHF") == 1
    assert "CLM_PMT_AMT" in tokens


def test_extract_column_tokens_caps_at_max_column_queries():
    text = " ".join(f"COL_{i}_NAME" for i in range(10))
    assert len(_extract_column_tokens(text)) == 6


# ── _reciprocal_rank_fusion ──────────────────────────────────────────────────

def test_rrf_ranks_a_chunk_found_by_both_methods_above_one_found_by_only_one():
    dense = ["only in dense", "found by both"]
    lexical = ["found by both", "only in lexical"]
    fused = _reciprocal_rank_fusion([dense, lexical])
    assert fused[0] == "found by both"


def test_rrf_includes_chunks_found_by_only_one_method():
    dense = ["dense only"]
    lexical = ["lexical only"]
    fused = _reciprocal_rank_fusion([dense, lexical])
    assert set(fused) == {"dense only", "lexical only"}


def test_rrf_favors_a_top_rank_in_one_list_over_a_low_rank_in_the_other():
    dense = ["strong dense hit", "weak", "weaker", "weakest"]
    lexical = ["unrelated 1", "unrelated 2", "unrelated 3", "unrelated 4"]
    fused = _reciprocal_rank_fusion([dense, lexical])
    assert fused[0] == "strong dense hit"


def test_rrf_handles_empty_lists():
    assert _reciprocal_rank_fusion([[], []]) == []
    assert _reciprocal_rank_fusion([["only chunk"], []]) == ["only chunk"]


# ── retrieve_grounded_knowledge ──────────────────────────────────────────────

def _patch_retrieval(dense_side_effect=None, dense_return=None, fts_side_effect=None, fts_return=None):
    dense_kwargs = {"side_effect": dense_side_effect} if dense_side_effect else {"return_value": dense_return or []}
    fts_kwargs = {"side_effect": fts_side_effect} if fts_side_effect else {"return_value": fts_return or []}
    return (
        patch("agents.domain_knowledge.retrieve_domain_knowledge", **dense_kwargs),
        patch("agents.domain_knowledge.retrieve_domain_knowledge_fts", **fts_kwargs),
    )


def test_retrieve_grounded_knowledge_skips_when_opted_out():
    p_dense, p_fts = _patch_retrieval()
    with p_dense as mock_dense, p_fts as mock_fts:
        result = retrieve_grounded_knowledge("SP_CHF question", {"use_domain_knowledge": False})

    assert result == ""
    mock_dense.assert_not_called()
    mock_fts.assert_not_called()


def test_retrieve_grounded_knowledge_skips_when_no_active_pack():
    p_dense, p_fts = _patch_retrieval()
    with patch("agents.domain_knowledge.get_active_pack_config", return_value={"pack_id": None}), \
         p_dense as mock_dense, p_fts as mock_fts:
        result = retrieve_grounded_knowledge("SP_CHF question", {"use_domain_knowledge": True})

    assert result == ""
    mock_dense.assert_not_called()
    mock_fts.assert_not_called()


def test_retrieve_grounded_knowledge_issues_a_dense_and_lexical_query_per_column():
    """Regression test for the silent sign-inversion bug: a whole-question embedding
    search alone missed the SP_* flag's documented 1=Yes/2=No coding even though it was
    indexed. The fix fuses a targeted dense query with a lexical (full-text) query for
    each column mentioned in the text."""
    def fake_dense(pack_id, query, top_k=5):
        if query == "sum of SP_CHF flags":
            return ["generic chronic condition chunk"]
        return []  # dense misses the specific fact for the column query, as observed

    def fake_fts(pack_id, query, top_k=5):
        return ["SP_CHF: 1=Yes, 2=No"]  # lexical search catches it instead

    p_dense, p_fts = _patch_retrieval(dense_side_effect=fake_dense, fts_side_effect=fake_fts)
    with patch("agents.domain_knowledge.get_active_pack_config", return_value={"pack_id": "medicare-claims"}), \
         p_dense as mock_dense, p_fts as mock_fts:
        result = retrieve_grounded_knowledge(
            "sum of SP_CHF flags", {"use_domain_knowledge": True, "domain_pack_id": "medicare-claims"}
        )

    assert "SP_CHF: 1=Yes, 2=No" in result
    assert "generic chronic condition chunk" in result
    assert mock_dense.call_count == 2  # one main-text query + one for the SP_CHF column
    assert mock_fts.call_count == 1    # lexical search only runs for column queries, not the main text
    fts_query = mock_fts.call_args.args[1] if mock_fts.call_args.args else mock_fts.call_args.kwargs.get("query")
    assert fts_query == "SP_CHF"  # lexical query is the bare literal token, not the elaborated dense query


def test_retrieve_grounded_knowledge_dedupes_and_caps_total_chunks():
    p_dense, p_fts = _patch_retrieval(
        dense_side_effect=lambda pack_id, query, top_k=5: ["shared chunk", f"unique dense for {query}"],
        fts_side_effect=lambda pack_id, query, top_k=5: ["shared chunk", f"unique lexical for {query}"],
    )
    with patch("agents.domain_knowledge.get_active_pack_config", return_value={"pack_id": "medicare-claims"}), \
         p_dense, p_fts:
        result = retrieve_grounded_knowledge(
            "SP_CHF SP_CNCR SP_COPD SP_DIABETES SP_RA_OA question",
            {"use_domain_knowledge": True},
        )

    assert result.count("shared chunk") == 1
    assert result.count("# Domain knowledge") == 1


def test_retrieve_grounded_knowledge_expands_wildcard_end_to_end():
    def fake_dense(pack_id, query, top_k=5):
        return ["SP_CHF: 1=Yes, 2=No"] if "SP_CHF" in query else ["generic chunk"]

    p_dense, p_fts = _patch_retrieval(dense_side_effect=fake_dense)
    state = {
        "use_domain_knowledge": True,
        "domain_pack_id": "medicare-claims",
        "data_descriptions": {"beneficiary.csv": "SP_CHF: int64\nSP_ALZHDMTA: int64"},
    }
    with patch("agents.domain_knowledge.get_active_pack_config", return_value={"pack_id": "medicare-claims"}), \
         p_dense, p_fts:
        result = retrieve_grounded_knowledge("sum of SP_* flags per beneficiary", state)

    assert "SP_CHF: 1=Yes, 2=No" in result


def test_retrieve_grounded_knowledge_returns_empty_string_on_retrieval_error():
    with patch("agents.domain_knowledge.get_active_pack_config", side_effect=RuntimeError("db down")):
        result = retrieve_grounded_knowledge("SP_CHF question", {"use_domain_knowledge": True})

    assert result == ""
