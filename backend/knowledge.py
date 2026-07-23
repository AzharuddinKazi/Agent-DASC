"""Domain pack knowledge base: ingest uploaded documents and retrieve relevant
chunks for the Planner. Plain chunk/embed/similarity-search — no knowledge
graph, no entity extraction.
"""

import io
import os

from google import genai
from google.genai import types
from pypdf import PdfReader
from docx import Document as DocxDocument

from db import supabase

_EMBED_MODEL = "gemini-embedding-001"
_EMBED_DIM = 768
# Embedding calls are small/fast — a much tighter bound than the 120s used for full
# generation calls (llm_router.py) is appropriate, but the point is the same: never let
# an API call hang the ingestion background task or a live Planner call indefinitely.
_EMBED_TIMEOUT_MS = 30_000

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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


def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        resp = _client.models.embed_content(
            model=_EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=_EMBED_DIM,
                http_options=types.HttpOptions(timeout=_EMBED_TIMEOUT_MS),
            ),
        )
        embeddings.append(resp.embeddings[0].values)
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
