-- Closes a cache-correctness gap in agents/analyzer.py's file_descriptions cache: it
-- previously kyed on filename + byte size alone, so two different files that happen to
-- share both a name and a size (re-dropped into data/ under the same filename, e.g.) would
-- silently serve the wrong cached description. Adds a cheap head/tail content fingerprint
-- (see analyzer._content_fingerprint — not a full-file hash, to avoid re-reading very large
-- datasets such as the 470MB file this repo ships with on every analyzer run) as a second
-- cache-validity check alongside file_size_bytes.
--
-- Applied directly against the live Supabase Postgres instance via SUPABASE_DB_URL (this
-- repo has no migration runner/tracked history yet — this file exists for documentation
-- and reproducibility, not automated application). Additive only, nullable (existing rows
-- without a hash simply miss the cache once and get backfilled on the next analyzer run —
-- see the `.get("content_hash")` fallback in analyzer.py). Safe to drop if ever abandoned:
--   ALTER TABLE file_descriptions DROP COLUMN IF EXISTS content_hash;

ALTER TABLE file_descriptions
  ADD COLUMN IF NOT EXISTS content_hash text;
