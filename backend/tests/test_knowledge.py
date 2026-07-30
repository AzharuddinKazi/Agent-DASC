from knowledge import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_returns_a_single_chunk_unmodified():
    text = "This is a short paragraph that easily fits in one chunk."
    assert chunk_text(text, chunk_size=1500) == [text]


def test_heading_and_short_paragraph_stay_in_one_chunk_with_no_duplicate_heading():
    text = "# Introduction\nThis is a short intro paragraph."
    chunks = chunk_text(text, chunk_size=1500)
    assert len(chunks) == 1
    # The heading line appears exactly once, not duplicated by the prefixing logic.
    assert chunks[0].count("# Introduction") == 1
    assert "This is a short intro paragraph." in chunks[0]


def test_numbered_list_items_are_never_split_across_chunks():
    """Regression case for the original bug this replaces: a numbered procedure's
    steps must survive intact, not get sliced mid-item by a blind character window."""
    text = "\n".join([
        "# Procedure",
        "1. Recode the SP_CHF flag so 1 means yes and 2 means no.",
        "2. Filter beneficiaries where the recoded flag is true.",
        "3. Compute the average total reimbursement for that group.",
        "4. Compare it against beneficiaries without the condition.",
    ])
    chunks = chunk_text(text, chunk_size=65, overlap=0)

    steps = [
        "1. Recode the SP_CHF flag so 1 means yes and 2 means no.",
        "2. Filter beneficiaries where the recoded flag is true.",
        "3. Compute the average total reimbursement for that group.",
        "4. Compare it against beneficiaries without the condition.",
    ]
    for step in steps:
        matches = [c for c in chunks if step in c]
        assert len(matches) == 1, f"step should appear whole in exactly one chunk: {step!r}"


def test_long_run_on_paragraph_splits_on_sentence_boundaries_not_mid_sentence():
    sentences = [
        "The KYC risk score is computed from four weighted factors.",
        "Each factor is normalised to a zero to one hundred scale.",
        "The composite score is the weighted sum of all four factors.",
        "A score above seventy five is classified as high risk.",
    ]
    text = " ".join(sentences)
    chunks = chunk_text(text, chunk_size=70, overlap=0)

    # Every sentence must appear intact (as a whole substring) somewhere — none cut
    # mid-word/mid-sentence by a raw character window.
    for sentence in sentences:
        assert any(sentence in c for c in chunks), f"sentence was split or lost: {sentence!r}"


def test_a_single_oversized_unit_falls_back_to_character_windowing():
    """A run-on unit with no sentence-ending punctuation at all (e.g. a huge table row
    or a URL) has no structure left to split on — must still produce bounded chunks
    covering the whole content, via the last-resort character window."""
    text = "x" * 500
    chunks = chunk_text(text, chunk_size=100, overlap=0)
    assert "".join(chunks) == text
    assert all(len(c) <= 100 for c in chunks)


def test_chunks_stay_close_to_the_requested_size():
    text = "\n\n".join(f"Paragraph number {i} with a bit of extra padding text." for i in range(30))
    chunks = chunk_text(text, chunk_size=200, overlap=0)
    assert len(chunks) > 1
    # Some slack allowed for the heading-prefix addition, but no runaway chunk.
    assert all(len(c) <= 260 for c in chunks)


def test_overlap_carries_the_last_unit_into_the_next_chunk():
    text = "\n\n".join([
        "First independent paragraph with enough content to matter here.",
        "Second independent paragraph with enough content to matter here.",
        "Third independent paragraph with enough content to matter here.",
    ])
    chunks = chunk_text(text, chunk_size=75, overlap=70)
    assert len(chunks) > 1
    # The end of one chunk should reappear at the start of the next.
    for i in range(len(chunks) - 1):
        tail_unit = chunks[i].split("\n\n")[-1]
        assert chunks[i + 1].startswith(tail_unit)


def test_section_heading_is_prefixed_onto_a_later_chunk_under_the_same_section():
    text = "\n".join([
        "# Risk Scoring",
        "1. First step is long enough on its own to force a chunk boundary soon after.",
        "2. Second step also long enough that it should land in a later chunk entirely.",
    ])
    chunks = chunk_text(text, chunk_size=90, overlap=0)
    assert len(chunks) > 1
    # Every chunk belongs to the "Risk Scoring" section — each must carry that context
    # either via the literal heading line or the prefix logic, not silently lose it.
    for c in chunks:
        assert "Risk Scoring" in c
