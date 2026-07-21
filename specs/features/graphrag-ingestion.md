# Feature Spec: GraphRAG Ingestion Pipeline

## Purpose
Allows analysts to upload SME (Subject Matter Expert) documents that are indexed into
Microsoft GraphRAG. The resulting knowledge graph (entities, relationships, communities)
is retrieved by the Planner agent to provide domain context before planning.

## User-Facing Behaviour

### Uploading a document
1. User navigates to `/knowledge` in the UI
2. Clicks "Upload Document"
3. Selects a file (PDF, DOCX, TXT, Markdown)
4. System accepts the upload, creates a `knowledge_documents` record with `graphrag_status: pending`
5. Returns immediately — indexing happens asynchronously in the background
6. UI polls `GET /knowledge/{doc_id}` or listens on WebSocket for status updates

### Indexing progress states
```
pending → indexing → indexed
                   → failed (with error_message)
```

### Viewing extracted knowledge
After indexing completes (`graphrag_status: indexed`), the document detail page shows:
- **Community cards** (primary view) — each GraphRAG community as a card with title + summary
- **Entity list** (secondary view) — table of extracted entities with type and description
- **Graph view** (optional, power users) — interactive React Flow / Cytoscape.js visualisation of entity nodes and relationship edges

### Deleting a document
- Removes the document record and all associated entities/communities from PostgreSQL
- Triggers Microsoft GraphRAG index rebuild (removes the document from the graph)
- Deletion is async — status shown in UI

## Technical Implementation

### Upload flow (`graphrag/ingestion.py`)
```
POST /knowledge/upload (multipart)
    → validate file type and size (max 50MB)
    → save file to DATA_DIR/knowledge/{doc_id}/{original_filename}
    → INSERT knowledge_documents (status: pending)
    → enqueue indexing task (APScheduler background job)
    → return 202 with document record
```

### Indexing pipeline (`graphrag/indexing.py`) [LOCKED: incremental update, not full reindex]
Microsoft GraphRAG indexing runs as a background job. New uploads use the `update` command
(GraphRAG v0.4+), which does delta detection (`get_delta_docs`) and re-uses cached
extraction results for already-indexed documents — only the new document is chunked and
entity-extracted from scratch. This was previously spec'd as a full `graphrag index`
rebuild on every upload, which would re-process the entire corpus each time; confirmed
against the official GraphRAG docs/repo that incremental `update` is the supported path
for additions (deletion still has no documented incremental path — see below).

```
1. Update status → "indexing"
2. Convert document to plain text
   - PDF: pdfplumber or PyMuPDF
   - DOCX: python-docx
   - TXT/MD: read directly
3. Write text to GraphRAG input directory
4. Run Microsoft GraphRAG incremental update:
   graphrag update --root {GRAPHRAG_ROOT} --method standard-update --verbose
5. Parse GraphRAG output:
   - entities.parquet → INSERT/UPDATE knowledge_entities
   - communities.parquet → INSERT/UPDATE knowledge_communities
   - relationships.parquet → store for graph view
6. Update status → "indexed", update entity/community/relationship counts
```

Note: community summarization can still be recomputed if the new content crosses certain
thresholds (per GraphRAG's own docs) — the cost warning below still applies, but no longer
assumes full-corpus reprocessing on every upload.

### GraphRAG configuration (`graphrag/settings.yaml`)
```yaml
llm:
  model: ${LLM_MODEL}          # claude-sonnet-4-6 (cloud) or ollama model (on-prem)
  api_base: ${LLM_API_BASE}    # Anthropic API or Ollama endpoint
  api_key: ${LLM_API_KEY}

embeddings:
  model: ${EMBEDDING_MODEL}    # text-embedding-3-small or local equivalent

storage:
  type: file
  base_dir: ${GRAPHRAG_ROOT}/output

chunk_size: 1200
chunk_overlap: 100
```

### Planner retrieval (`graphrag/retrieval.py`)
Called at the start of every Planner node execution:

```python
def retrieve_graphrag_context(question: str, summaries: str) -> GraphRAGContext:
    # Local search — specific entity/relationship retrieval
    local_results = graphrag_local_search(
        query=f"{question}\n\nAvailable data:\n{summaries}",
        top_k=10
    )
    # Global search — community summary retrieval
    global_results = graphrag_global_search(
        query=question,
        top_k=5
    )
    return GraphRAGContext(
        relevant_entities=local_results.entities,
        relevant_relationships=local_results.relationships,
        community_summaries=global_results.community_summaries
    )
```

Context is appended to `{filenames_and_summaries}` in Planner prompts as:
```
# Domain Knowledge
{community_summaries}

# Relevant Entities
{relevant_entities}
```

### Cost warning [LOCKED]
Microsoft GraphRAG indexing makes many LLM calls. Before indexing begins:
- Estimate token cost from the NEW file's size: `(file_size_bytes / 4) * indexing_multiplier`
  (approx 15x) — this covers the guaranteed cost (chunking + entity extraction of the new
  document, which always happens in full)
- Community summarization recompute cost is not reliably predictable ahead of time (depends
  on how much the new content perturbs existing communities), so the UI shows the
  guaranteed-cost estimate plus a note: "community re-summarization may add cost beyond
  this estimate for large knowledge bases"
- If estimated cost > configurable threshold (default: $5.00), show warning in UI before proceeding
- Users can dismiss warning and continue, or cancel

### Index rebuild on deletion [confirmed against GraphRAG docs — no change from original spec]
Deleting a document requires rebuilding the GraphRAG index without that document. Unlike
uploads (now incremental via `update`), deletion has no documented incremental path in
GraphRAG — this is the one place a full rebuild is genuinely required:
- Remove document from GraphRAG input directory
- Re-run `graphrag index` (full rebuild)
- Update PostgreSQL: delete entities/communities for the document
- For large knowledge bases, rebuild can take minutes — status shown in UI

## Storage Layout
```
DATA_DIR/
└── knowledge/
    └── {doc_id}/
        └── {original_filename}   ← uploaded file

GRAPHRAG_ROOT/
├── input/                        ← GraphRAG reads from here
│   └── {doc_id}.txt              ← extracted plain text
├── output/                       ← GraphRAG writes here
│   ├── entities.parquet
│   ├── communities.parquet
│   └── relationships.parquet
└── settings.yaml
```

## Data Model (from database-schema.sql)
- `knowledge_documents` — one row per uploaded document
- `knowledge_entities` — extracted entities, FK to knowledge_documents
- `knowledge_communities` — extracted communities, FK to knowledge_documents

## Error Handling
| Error | Behaviour |
|---|---|
| Unsupported file type | 415 response, file not saved |
| File > 50MB | 413 response |
| GraphRAG indexing failure | `graphrag_status: failed`, `error_message` set, user notified |
| LLM API error during indexing | Retry up to 3 times with exponential backoff, then fail |
| PDF extraction failure | Try fallback extractor (PyMuPDF → pdfplumber), then fail with message |
| Index rebuild failure on delete | Document marked "delete_pending", rebuild retried on next upload |

## On-prem Consideration
On-prem deployments use Ollama as the LLM for GraphRAG indexing. GraphRAG must be configured with an Ollama-compatible endpoint. Embedding model also switches to a local model (e.g. `nomic-embed-text` via Ollama).

## Security Rules
- Uploaded files stored in `DATA_DIR/knowledge/` — path traversal MUST be prevented
  (`secure_filename()` applied to original filename)
- File contents MUST NOT be returned in API responses — only metadata
- GraphRAG indexing runs as a background job — LLM API key MUST NOT be logged

## Test Scenarios

### Unit
- Valid PDF upload → 202, record created with status "pending"
- File > 50MB → 413
- Unsupported extension (.exe) → 415
- Cost estimate calculated correctly from file size
- Plain text extraction works for PDF, DOCX, TXT, Markdown

### Integration (real GraphRAG + test fixture)
- Uploading a 5-page test PDF results in `graphrag_status: indexed` with non-zero entity/community counts
- `GET /knowledge/{doc_id}` returns entities and community summaries after indexing
- Planner retrieval returns non-empty GraphRAGContext for a query matching test document content
- Deleting a document and re-indexing removes its entities from the knowledge graph
