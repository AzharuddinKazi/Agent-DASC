"""Domain pack knowledge base: ingest uploaded documents and retrieve relevant
chunks for the Planner/Coder/Verifier. Two retrieval paths: dense embedding similarity
(this module's original design) and Postgres full-text search (added alongside it, not
replacing it) — see agents/domain_knowledge.py for why both exist and how they're fused.

Embeddings go through the same OpenAI-compatible endpoint as llm_router.py's chat
completions (OPENROUTER_BASE_URL) — as of 2026-08, a local Ollama server, using
nomic-embed-text (768 dims, ~274MB, no GPU contention worth worrying about — it runs
alongside whatever chat model is loaded without evicting it in practice). Previously
OpenRouter's nvidia/nemotron-3-embed-1b:free (2048 dims); before that, Gemini (768
dims). domain_pack_chunks.embedding is vector(768) as of
migrations/2026-08-22_domain_pack_chunks_local_embeddings.sql — see that file if this
ever needs to change again, including why an in-place dimension change only works on
an empty table. No HNSW index regardless of model — at this corpus size (hundreds to
low thousands of chunks) exact brute-force cosine search (see
match_domain_pack_chunks) is plenty fast without an ANN index.

Full-text search runs off a generated `content_tsv` tsvector column + GIN index (see
migrations/2026-07-29_domain_pack_chunks_fts.sql) and match_domain_pack_chunks_fts —
same corpus-size reasoning applies: no need for anything beyond Postgres's built-in
text search at this scale.
"""

import io
import os
import re

import requests
from pypdf import PdfReader
from docx import Document as DocxDocument

from db import supabase

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "nvidia/nemotron-3-embed-1b:free")
# Embedding calls are small/fast — a much tighter bound than the 120s used for full
# generation calls (llm_router.py) is appropriate, but the point is the same: never let
# an API call hang the ingestion background task or a live Planner call indefinitely.
_EMBED_TIMEOUT_S = 30


def extract_text(filename: str, raw_bytes: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "docx":
        doc = DocxDocument(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    if ext in ("txt", "md"):
        return raw_bytes.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: .{ext}")


_HEADING_RE  = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")


def _split_into_units(text: str) -> list[tuple[str, str]]:
    """Splits raw document text into (heading, unit_text) pairs along natural
    boundaries — markdown headings, blank-line-separated paragraphs, and individual
    list items — instead of a blind character count. A numbered procedure's steps are
    each their own unit and are never merged with unrelated surrounding prose, and a
    unit is never split mid-sentence/mid-item unless it's larger than chunk_size on its
    own (see _chunk_unit below). `heading` is the most recent heading line seen, carried
    forward onto every unit under it, so a chunk built from these units keeps its
    section context even if the heading itself ended up in an earlier chunk.
    """
    units, current_heading, paragraph_lines = [], "", []

    def flush_paragraph():
        if not paragraph_lines:
            return
        para = "\n".join(paragraph_lines).strip()
        paragraph_lines.clear()
        if not para:
            return
        # Each list item is its own unit (steps of a procedure must stay individually
        # addressable), but non-list prose within the same paragraph stays merged.
        lines = para.split("\n")
        buf = []
        for line in lines:
            if _LIST_ITEM_RE.match(line):
                if buf:
                    units.append((current_heading, "\n".join(buf).strip()))
                    buf = []
                units.append((current_heading, line.strip()))
            else:
                buf.append(line)
        if buf:
            units.append((current_heading, "\n".join(buf).strip()))

    for line in text.split("\n"):
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            current_heading = heading_match.group(2).strip()
            units.append((current_heading, line.strip()))
        elif line.strip() == "":
            flush_paragraph()
        else:
            paragraph_lines.append(line)
    flush_paragraph()

    return [(h, u) for h, u in units if u]


def _chunk_unit(unit: str, chunk_size: int) -> list[str]:
    """A single unit (paragraph or list item) larger than chunk_size can't be packed
    whole — split it on sentence boundaries first (keeps a sentence intact), and only
    fall back to a raw character window for a single run-on sentence/table row that's
    still too large on its own. This is the one place raw windowing still happens, and
    only as a last resort for content with no usable structure at all."""
    if len(unit) <= chunk_size:
        return [unit]
    pieces, buf = [], ""
    for sentence in _SENTENCE_SPLIT_RE.split(unit):
        candidate = f"{buf} {sentence}".strip() if buf else sentence
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            if len(sentence) <= chunk_size:
                buf = sentence
            else:
                for start in range(0, len(sentence), chunk_size):
                    pieces.append(sentence[start:start + chunk_size])
                buf = ""
    if buf:
        pieces.append(buf)
    return pieces


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Structure-aware chunking: split on markdown headings/paragraphs/list items
    (_split_into_units), then greedily pack consecutive units into ~chunk_size chunks
    without ever splitting a unit across a chunk boundary — unlike a blind sliding
    character window, a numbered step or a fact can't get sliced in half. Each chunk is
    prefixed with its section heading (when known) so retrieval keeps that context even
    though the heading line itself may live in an earlier chunk. `overlap` carries the
    last unit of one chunk forward as the start of the next, preserving the original
    chunker's boundary-continuity property without re-slicing by raw character count.
    """
    text = text.strip()
    if not text:
        return []

    units = _split_into_units(text)
    if not units:
        return []

    chunks: list[str] = []
    # The heading this chunk STARTS under — set once when a chunk begins, not updated
    # as later units (possibly under a different heading) get packed in. A chunk that
    # happens to span a section boundary should describe where it begins, not whichever
    # heading was most recently seen when it was flushed.
    chunk_start_heading = ""
    current_units: list[str] = []
    current_len = 0

    def flush_chunk():
        if not current_units:
            return
        body = "\n\n".join(current_units)
        prefix = (
            f"{chunk_start_heading}\n\n"
            if chunk_start_heading and chunk_start_heading not in current_units[0]
            else ""
        )
        chunks.append((prefix + body).strip())

    for heading, unit in units:
        for piece in _chunk_unit(unit, chunk_size):
            piece_len = len(piece) + 2  # matches the "\n\n".join separator above
            if current_units and current_len + piece_len > chunk_size:
                flush_chunk()
                # Carry the last unit forward as overlap, same purpose as the original
                # fixed-window overlap — bounded so one huge unit can't itself become
                # the whole of the next chunk's "overlap".
                carry = current_units[-1] if current_units and len(current_units[-1]) <= overlap else None
                current_units = [carry] if carry else []
                current_len = len(carry) + 2 if carry else 0
                chunk_start_heading = heading
            if not current_units:
                chunk_start_heading = heading
            current_units.append(piece)
            current_len += piece_len
    flush_chunk()

    return chunks


_EMBED_BATCH_SIZE = 50  # keeps request payloads small; a large document can have 100+ chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embeddings = []
    for start in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[start:start + _EMBED_BATCH_SIZE]
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": _EMBED_MODEL, "input": batch},
            timeout=_EMBED_TIMEOUT_S,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter embeddings call failed: {response.status_code} {response.text[:500]}")
        data = sorted(response.json()["data"], key=lambda row: row["index"])
        embeddings.extend(row["embedding"] for row in data)
    return embeddings


def ingest_document(pack_id: str, document_id: str, filename: str, raw_bytes: bytes):
    try:
        text = extract_text(filename, raw_bytes)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No extractable text found in document")

        embeddings = embed_texts(chunks)

        rows = [
            {
                "document_id": document_id,
                "pack_id": pack_id,
                "chunk_index": i,
                "content": chunk,
                "embedding": embedding,
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        supabase.table("domain_pack_chunks").insert(rows).execute()

        supabase.table("domain_pack_documents").update({
            "status": "ready",
            "chunk_count": len(chunks),
        }).eq("id", document_id).execute()
    except Exception as e:
        supabase.table("domain_pack_documents").update({
            "status": "failed",
            "error": str(e),
        }).eq("id", document_id).execute()


def retrieve_domain_knowledge(pack_id: str | None, query: str, top_k: int = 5) -> list[str]:
    if not pack_id:
        return []
    query_embedding = embed_texts([query])[0]
    resp = supabase.rpc("match_domain_pack_chunks", {
        "query_embedding": query_embedding,
        "match_pack_id": pack_id,
        "match_count": top_k,
    }).execute()
    return [row["content"] for row in resp.data]


def retrieve_domain_knowledge_fts(pack_id: str | None, query: str, top_k: int = 5) -> list[str]:
    """Lexical (BM25-style) retrieval via Postgres full-text search — complements
    `retrieve_domain_knowledge`'s dense embedding search, see agents/domain_knowledge.py
    for why: dense search can miss a specific literal fact (e.g. a documented value
    coding) when the surrounding chunk text doesn't semantically echo the query, in a
    way exact lexical matching structurally can't. Uses `websearch_to_tsquery`, which
    tolerates multi-word queries the way a search-box user would type them; a query with
    no matching lexeme (e.g. it's all stopwords, or nothing in the corpus mentions it)
    just returns no rows rather than erroring.
    """
    if not pack_id:
        return []
    resp = supabase.rpc("match_domain_pack_chunks_fts", {
        "query_text": query,
        "match_pack_id": pack_id,
        "match_count": top_k,
    }).execute()
    return [row["content"] for row in resp.data]
