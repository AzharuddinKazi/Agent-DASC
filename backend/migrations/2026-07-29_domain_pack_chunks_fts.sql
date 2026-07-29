-- Adds full-text search alongside the existing dense (pgvector) retrieval on
-- domain_pack_chunks, for fusion via reciprocal rank fusion in agents/domain_knowledge.py.
--
-- Why: dense embedding search structurally misses precise, literal facts (e.g. a
-- column's documented value-coding) when the surrounding chunk text doesn't semantically
-- echo the query — reproduced concretely against this database (see agents/
-- domain_knowledge.py's docstring). BM25-style lexical matching is the right primitive
-- for column-name-shaped queries; embeddings stay the right primitive for narrative/
-- thematic queries. This migration adds the lexical half.
--
-- Applied directly against the live Supabase Postgres instance via SUPABASE_DB_URL
-- (this repo has no migration runner/tracked history yet — this file exists for
-- documentation and reproducibility, not automated application). Additive only: a new
-- generated column, a new index, a new function. Safe to re-run (IF NOT EXISTS / OR
-- REPLACE throughout) and safe to drop if this approach is ever abandoned:
--   DROP FUNCTION IF EXISTS match_domain_pack_chunks_fts;
--   DROP INDEX IF EXISTS idx_domain_pack_chunks_content_tsv;
--   ALTER TABLE domain_pack_chunks DROP COLUMN IF EXISTS content_tsv;

ALTER TABLE domain_pack_chunks
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_domain_pack_chunks_content_tsv
  ON domain_pack_chunks USING gin (content_tsv);

CREATE OR REPLACE FUNCTION match_domain_pack_chunks_fts(
  query_text text,
  match_pack_id text,
  match_count integer DEFAULT 5
)
RETURNS TABLE(content text, rank double precision)
LANGUAGE sql
STABLE
AS $$
  SELECT content, ts_rank(content_tsv, websearch_to_tsquery('english', query_text)) AS rank
  FROM domain_pack_chunks
  WHERE pack_id = match_pack_id
    AND content_tsv @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
$$;
