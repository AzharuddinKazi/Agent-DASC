-- DS-STAR local Postgres schema
--
-- Generated from a `pg_dump --schema-only --schema=public` of the live Supabase project
-- (2026-08-22), then hand-sanitized for a single-machine local deployment behind
-- self-hosted PostgREST (see TASKS.md "Supabase -> local Docker Postgres migration"):
--   - Dropped `checkpoint_blobs`/`checkpoint_writes`/`checkpoints`/`checkpoint_migrations` —
--     langgraph-checkpoint-postgres creates these itself on first connection, they don't
--     belong in a hand-maintained schema file.
--   - Dropped all ROW LEVEL SECURITY / POLICY statements and the two foreign keys into
--     `auth.users` (`domain_pack_documents.uploaded_by`, `tasks.user_id`) — there is no
--     `auth` schema in this deployment, auth is dropped entirely in favor of one fixed
--     local user (see backend/auth.py). The columns themselves are kept as plain nullable
--     uuid columns since app code still reads/writes them.
--   - Dropped `supabase_vault` (confirmed unused by any app code) and `pg_stat_statements`
--     (needs `shared_preload_libraries` set at server start, not just CREATE EXTENSION;
--     it's a stats-introspection extension, nothing in the app depends on it).
--   - Added the `dsstar_app` role PostgREST impersonates for every request (see
--     docker-compose.yml's `PGRST_DB_ANON_ROLE`) with grants on all app tables.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

--
-- Tables
--
-- (Table bodies come before the functions below on purpose: the functions' SQL bodies are
-- validated at CREATE FUNCTION time, so `tasks`/`domain_pack_chunks` must already exist.)

CREATE TABLE public.app_settings (
    key text NOT NULL,
    value text
);

CREATE TABLE public.domain_pack_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    pack_id text NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    -- 2048 dims matches OpenRouter's nvidia/nemotron-3-embed-1b:free (the default
    -- embedding model — see backend/knowledge.py). Was briefly vector(768) for a local
    -- Ollama nomic-embed-text setup, reverted 2026-08-23 — see
    -- migrations/2026-08-23_domain_pack_chunks_openrouter_embeddings.sql.
    embedding public.vector(2048) NOT NULL,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, content)) STORED
);

CREATE TABLE public.domain_pack_configs (
    pack_id text NOT NULL,
    report_persona text NOT NULL,
    report_classification text,
    subquestion_dimensions text[] DEFAULT '{}'::text[] NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name text DEFAULT ''::text NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    dataset_generator text,
    example_question text
);

CREATE TABLE public.domain_pack_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    pack_id text NOT NULL,
    filename text NOT NULL,
    status text DEFAULT 'processing'::text NOT NULL,
    error text,
    chunk_count integer DEFAULT 0 NOT NULL,
    uploaded_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.file_descriptions (
    filename text NOT NULL,
    description text,
    file_size_bytes bigint,
    analyzed_at timestamp with time zone DEFAULT now(),
    content_hash text
);

CREATE TABLE public.tasks (
    task_id uuid NOT NULL,
    query text NOT NULL,
    formatting_guidelines text DEFAULT ''::text,
    status text DEFAULT 'queued'::text,
    created_at timestamp with time zone DEFAULT now(),
    final_result text,
    rounds_taken integer,
    current_agent text,
    current_script text,
    cumulative_plan jsonb DEFAULT '[]'::jsonb,
    task_type text DEFAULT 'qa'::text,
    sub_results text,
    logs jsonb DEFAULT '[]'::jsonb,
    user_id uuid
);

-- Added 2026-08-23 for real Google OAuth login (see TASKS.md "Google OAuth login + Admin
-- Control Panel") — replaces the single-fixed-local-user stub. `google_sub` is Google's
-- stable per-account id (the JWT's `sub` claim), the actual identity key; `id` stays a
-- separate app-local uuid so `tasks.user_id` and every other FK-shaped column keeps its
-- existing type. `is_admin` is recomputed from the ADMIN_EMAILS env var on every login,
-- not hand-edited here, so it can't drift from the allowlist backend/auth.py enforces.
-- google_sub/email are nullable: also added 2026-08-24 for guest (name-only) login for
-- colleagues on office laptops where Gmail is deactivated — see the guest_login migration.
-- auth_provider distinguishes the two; guests never have a google_sub/email and can never
-- match ADMIN_EMAILS, so they can never become admin.
CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    google_sub text,
    email text,
    name text,
    picture_url text,
    auth_provider text DEFAULT 'google' NOT NULL,
    is_admin boolean DEFAULT false NOT NULL,
    is_banned boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_sign_in_at timestamp with time zone,
    CONSTRAINT users_auth_provider_check CHECK (auth_provider IN ('google', 'guest')),
    CONSTRAINT users_guest_name_check CHECK (auth_provider <> 'guest' OR name IS NOT NULL)
);

-- Admin-editable prompt/model overrides (Admin Control Panel, same date). Empty table =
-- no behavior change from today's hardcoded defaults — each agent reads its row here first,
-- falling back to its own Python constant / tier lookup if absent (see
-- backend/agents/prompt_store.py, llm_router.py's agent_model_overrides check).
CREATE TABLE public.agent_prompts (
    agent_name text NOT NULL,
    prompt_text text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);

CREATE TABLE public.agent_model_overrides (
    agent_name text NOT NULL,
    model_id text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);

--
-- Constraints, indexes
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);

ALTER TABLE ONLY public.domain_pack_chunks
    ADD CONSTRAINT domain_pack_chunks_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.domain_pack_configs
    ADD CONSTRAINT domain_pack_configs_pkey PRIMARY KEY (pack_id);

ALTER TABLE ONLY public.domain_pack_documents
    ADD CONSTRAINT domain_pack_documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.file_descriptions
    ADD CONSTRAINT file_descriptions_pkey PRIMARY KEY (filename);

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (task_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

CREATE UNIQUE INDEX users_guest_name_unique ON public.users (lower(name)) WHERE auth_provider = 'guest';

ALTER TABLE ONLY public.agent_prompts
    ADD CONSTRAINT agent_prompts_pkey PRIMARY KEY (agent_name);

ALTER TABLE ONLY public.agent_model_overrides
    ADD CONSTRAINT agent_model_overrides_pkey PRIMARY KEY (agent_name);

CREATE INDEX idx_domain_pack_chunks_content_tsv ON public.domain_pack_chunks USING gin (content_tsv);

CREATE INDEX idx_domain_pack_chunks_pack_id ON public.domain_pack_chunks USING btree (pack_id);

CREATE INDEX idx_tasks_user_id ON public.tasks USING btree (user_id);

ALTER TABLE ONLY public.domain_pack_chunks
    ADD CONSTRAINT domain_pack_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.domain_pack_documents(id) ON DELETE CASCADE;

--
-- Functions
--

CREATE FUNCTION public.append_task_log(p_task_id text, p_entry jsonb) RETURNS void
    LANGUAGE sql
    AS $$
  UPDATE tasks
  SET logs = COALESCE(logs, '[]'::jsonb) || jsonb_build_array(p_entry)
  WHERE task_id = p_task_id::uuid;
$$;

CREATE FUNCTION public.match_domain_pack_chunks(query_embedding public.vector, match_pack_id text, match_count integer DEFAULT 5) RETURNS TABLE(content text, similarity double precision)
    LANGUAGE sql STABLE
    AS $$
    SELECT content, 1 - (embedding <=> query_embedding) AS similarity
    FROM domain_pack_chunks
    WHERE pack_id = match_pack_id
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE FUNCTION public.match_domain_pack_chunks_fts(query_text text, match_pack_id text, match_count integer DEFAULT 5) RETURNS TABLE(content text, rank double precision)
    LANGUAGE sql STABLE
    AS $$
  SELECT content, ts_rank(content_tsv, websearch_to_tsquery('english', query_text)) AS rank
  FROM domain_pack_chunks
  WHERE pack_id = match_pack_id
    AND content_tsv @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
$$;

--
-- PostgREST role
--
-- PGRST_DB_ANON_ROLE (docker-compose.yml) is the fallback for anonymous requests; the JWTs
-- backend/.env hands PostgREST also carry `{"role": "dsstar_app"}` explicitly, so every
-- request — anonymous or bearer-token — resolves to this same role. See TASKS.md "The
-- auth-removal mechanism" for why unsetting PGRST_JWT_SECRET (the original plan) doesn't
-- actually work with supabase-py's client.

CREATE ROLE dsstar_app NOLOGIN;
GRANT USAGE ON SCHEMA public TO dsstar_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dsstar_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dsstar_app;
