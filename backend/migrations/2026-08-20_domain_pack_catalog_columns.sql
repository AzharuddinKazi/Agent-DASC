-- Moves the domain pack catalog (name, description, tags, dataset generator, example
-- question) out of the hardcoded domain_packs/catalog.py Python list and into
-- domain_pack_configs, so GET /api/v1/domain_packs is entirely DB-backed instead of half
-- DB (persona/classification/dimensions) and half source code (everything else).
--
-- Why: domain_pack_configs already held a pack's *prompt* config; catalog.py held its
-- *browsing* metadata. Two sources of truth for "what domain packs exist" meant wiping
-- domain_pack_configs (e.g. for a fresh environment) never actually emptied the Domain
-- Packs page — the catalog list came back from code regardless of DB state. See main.py
-- for the corresponding endpoint changes.
--
-- Applied directly against the live Supabase Postgres instance via SUPABASE_DB_URL (same
-- convention as 2026-07-29_domain_pack_chunks_fts.sql — no migration runner/tracked
-- history yet). Additive only: five new nullable/defaulted columns, no data loss. Safe to
-- re-run (IF NOT EXISTS throughout) and safe to drop if this approach is ever abandoned:
--   ALTER TABLE domain_pack_configs DROP COLUMN IF EXISTS name;
--   ALTER TABLE domain_pack_configs DROP COLUMN IF EXISTS description;
--   ALTER TABLE domain_pack_configs DROP COLUMN IF EXISTS tags;
--   ALTER TABLE domain_pack_configs DROP COLUMN IF EXISTS dataset_generator;
--   ALTER TABLE domain_pack_configs DROP COLUMN IF EXISTS example_question;

ALTER TABLE domain_pack_configs
  ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  -- Filename of a dataset-generator script shipped alongside the backend (e.g.
  -- "generate_synthetic_data.py"), relative to BACKEND_DIR — NULL means the pack has no
  -- synthetic generator (matches catalog.py's has_dataset_generator flag semantics).
  ADD COLUMN IF NOT EXISTS dataset_generator TEXT,
  ADD COLUMN IF NOT EXISTS example_question TEXT;
