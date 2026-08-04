"""Column-aware domain-knowledge retrieval, shared by planner/coder/verifier.

A single embedding-similarity search against a whole compound question (e.g. "What is
the regression coefficient for the count of chronic conditions (sum of SP_* flags)
predicting total reimbursement, after adjusting for age and sex?") reliably favors
generic chunks about the topic in general over a specific, load-bearing fact like "this
column is coded 1=Yes, 2=No, not 0/1" — even when that exact fact is indexed. Verified
against a real run: the medicare-claims pack's own de10_codebook.pdf has the precise
"1 Yes / 2 No" coding table for every SP_* flag, but a whole-question query missed it,
and the resulting script summed the raw 1/2 codes as if they were 0/1 — silently
inverting a regression coefficient's sign in a regulatory-facing report.

Column names are a strong, cheap signal that a whole-question embedding drowns out:
issuing one extra targeted retrieval per column mentioned in the text (in addition to the
whole-text query) makes precise codebook facts about those specific columns dramatically
more likely to surface, regardless of the surrounding question's phrasing.

One wrinkle discovered while verifying this against the actual bug it's meant to catch:
questions/plan steps frequently refer to a *family* of columns by wildcard shorthand
("sum of SP_* flags") rather than naming any single one literally — "SP_*" itself isn't
a real column and doesn't retrieve anything useful. `_expand_wildcard_prefixes` resolves
that shorthand against the real column names the Analyzer already captured in
state["data_descriptions"], so "SP_*" becomes SP_CHF, SP_ALZHDMTA, etc. — the actual
literal names the codebook indexes facts under.

Column-name queries also get a second retrieval path fused in: Postgres full-text search
(match_domain_pack_chunks_fts) alongside the existing dense embedding search, combined
via reciprocal rank fusion. Dense search alone can still miss a specific literal fact if
the chunk containing it happens to emphasize other terms more (ts_rank isn't the fix for
that — it's a term-frequency measure, not semantic relevance) — but the two retrieval
methods fail in different, largely uncorrelated ways for a literal identifier like a
column name, so their union is where the actual precision gain comes from, not either
one individually. The whole-question query stays dense-only: it's inherently a semantic/
thematic lookup (narrative report grounding, broad hypothesis coverage), which is exactly
what embeddings are suited for and what BM25-style matching is not.
"""

import re

from domain_pack import get_active_pack_config
from knowledge import retrieve_domain_knowledge, retrieve_domain_knowledge_fts
from agents.prompt_safety import wrap_untrusted

# Column names in this pipeline's datasets are upper snake case with at least one
# underscore (SP_CHF, BENE_BIRTH_DT, CLM_PMT_AMT, HCPCS_CD_1, ...) — long enough to rule
# out incidental all-caps words like "USA" or acronyms used in prose.
_COLUMN_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

# Shorthand for "all columns starting with this prefix", e.g. "SP_*" or "ICD9_DGNS_CD_*".
_WILDCARD_PREFIX = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_)\*")

# A real column name as it appears in an Analyzer file description, e.g. "SP_CHF: int64"
# or a bare "SP_CHF" in a printed column list.
_REAL_COLUMN_NAME = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

MAX_COLUMN_QUERIES = 6
MAX_WILDCARD_EXPANSIONS_PER_PREFIX = 3
CHUNKS_PER_COLUMN = 2
CHUNKS_FOR_MAIN_QUERY = 3
MAX_TOTAL_CHUNKS = 10

# Candidate pool fetched from each retrieval method per column, before RRF narrows it
# down to CHUNKS_PER_COLUMN — wider than the final cut so fusion has something to fuse.
CANDIDATES_PER_METHOD = 5

# Standard RRF damping constant (Cormack et al.) — large enough that a chunk ranked #1
# by only one method still beats one ranked #2-3 by both, without letting a single
# method's ordering dominate the fused result entirely.
RRF_K = 60


def _reciprocal_rank_fusion(ranked_lists: list[list[str]]) -> list[str]:
    """Merges multiple best-first ranked lists of chunk text into one, by summing
    1/(RRF_K + rank) across whichever lists each chunk appears in. A chunk found by both
    dense and lexical search outranks one found by only one, and a chunk ranked highly by
    either method alone still surfaces near the top — this is what makes the fusion
    resilient to either method individually missing the right chunk."""
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list):
            scores[chunk] = scores.get(chunk, 0.0) + 1.0 / (RRF_K + rank + 1)
    return [chunk for chunk, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def _expand_wildcard_prefixes(text: str, data_descriptions: dict) -> list[str]:
    """Resolves "SP_*"-style shorthand in `text` against the real column names visible
    in the Analyzer's file descriptions, so retrieval can be grounded on literal names
    (e.g. SP_CHF) instead of a wildcard pattern that matches nothing in the index."""
    prefixes = list(dict.fromkeys(_WILDCARD_PREFIX.findall(text or "")))
    if not prefixes or not data_descriptions:
        return []
    all_columns = set()
    for desc in data_descriptions.values():
        all_columns.update(_REAL_COLUMN_NAME.findall(desc or ""))
    expanded = []
    for prefix in prefixes:
        matches = sorted(c for c in all_columns if c.startswith(prefix))
        expanded.extend(matches[:MAX_WILDCARD_EXPANSIONS_PER_PREFIX])
    return expanded


def _extract_column_tokens(text: str, data_descriptions: dict | None = None) -> list[str]:
    """Wildcard expansions come first — a "SP_*"-style reference to a whole column
    family is exactly the shape of question most likely to hide a per-flag encoding
    gotcha, so it should win the limited query budget over individually-named columns
    that are far more likely to be plain numeric/string fields with nothing to get wrong."""
    seen, tokens = set(), []
    for match in [*_expand_wildcard_prefixes(text, data_descriptions or {}), *_COLUMN_TOKEN.findall(text or "")]:
        if match not in seen:
            seen.add(match)
            tokens.append(match)
    return tokens[:MAX_COLUMN_QUERIES]


def retrieve_grounded_knowledge(text: str, state: dict) -> str:
    """Returns a formatted "# Domain knowledge" prompt section, or "" when knowledge is
    opted out, no pack is active, or nothing relevant is indexed.

    `text` is whatever the caller most needs grounded — the question for planner/verifier,
    the plan step being implemented for coder — since column mentions in that text drive
    the extra targeted queries.
    """
    if not state.get("use_domain_knowledge", True):
        return ""
    try:
        pack_id = get_active_pack_config(state.get("domain_pack_id"))["pack_id"]
        if not pack_id:
            return ""

        seen, chunks = set(), []
        for chunk in retrieve_domain_knowledge(pack_id, text, top_k=CHUNKS_FOR_MAIN_QUERY):
            if chunk not in seen:
                seen.add(chunk)
                chunks.append(chunk)

        for token in _extract_column_tokens(text, state.get("data_descriptions")):
            column_query = f"{token} column meaning and value coding"
            dense_hits = retrieve_domain_knowledge(pack_id, column_query, top_k=CANDIDATES_PER_METHOD)
            lexical_hits = retrieve_domain_knowledge_fts(pack_id, token, top_k=CANDIDATES_PER_METHOD)
            fused = _reciprocal_rank_fusion([dense_hits, lexical_hits])
            for chunk in fused[:CHUNKS_PER_COLUMN]:
                if chunk not in seen:
                    seen.add(chunk)
                    chunks.append(chunk)
    except Exception:
        chunks = []

    if not chunks:
        return ""
    joined = "\n\n".join(chunks[:MAX_TOTAL_CHUNKS])
    return f"""
    # Domain knowledge
    Reference material for this domain — use it to plan/code/verify like a subject-matter
    expert, not just a technical one. Pay special attention to any documented value
    coding for columns you use (e.g. flags coded 1/2 instead of 0/1) — using a raw code
    as if it were already a clean count or boolean is a common, silent correctness bug.
    {wrap_untrusted("domain_knowledge_reference", joined)}
"""
