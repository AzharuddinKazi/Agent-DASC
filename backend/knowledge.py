"""Domain pack knowledge base: ingest uploaded documents and retrieve relevant
chunks for the Planner. Plain chunk/embed/similarity-search — no knowledge
graph, no entity extraction.

Embeddings go through OpenRouter (same provider as llm_router.py's chat completions),
using nvidia/nemotron-3-embed-1b:free — genuinely free (verified: usage.cost == 0 on a
live call), unlike most of OpenRouter's other embedding-capable models which proxy to
paid providers. Its native output is 2048 dimensions, which is why
domain_pack_chunks.embedding is vector(2048) (migrated from vector(768) when this
model replaced Gemini) with no HNSW index — pgvector's HNSW caps at 2000 dims for the
plain vector type, and at this corpus size (hundreds to low thousands of chunks) exact
brute-force cosine search (see match_domain_pack_chunks) is plenty fast without an ANN
index anyway.
"""

import io
import os

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


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
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
