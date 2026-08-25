-- Google OAuth login + Admin Control Panel (see TASKS.md).
--
-- For the already-running local Postgres started before this change (fresh installs get
-- this via db/init.sql instead, which now includes the same tables). Apply with e.g.:
--   docker compose exec -T postgres psql -U postgres -d postgres < backend/migrations/2026-08-23_users_and_admin_config.sql
--
-- Idempotent (IF NOT EXISTS everywhere) so re-running it is harmless.

CREATE TABLE IF NOT EXISTS public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    google_sub text NOT NULL,
    email text NOT NULL,
    name text,
    picture_url text,
    is_admin boolean DEFAULT false NOT NULL,
    is_banned boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_sign_in_at timestamp with time zone
);

ALTER TABLE public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE public.users
    ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub);

ALTER TABLE public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

CREATE TABLE IF NOT EXISTS public.agent_prompts (
    agent_name text NOT NULL,
    prompt_text text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);

ALTER TABLE public.agent_prompts
    ADD CONSTRAINT agent_prompts_pkey PRIMARY KEY (agent_name);

CREATE TABLE IF NOT EXISTS public.agent_model_overrides (
    agent_name text NOT NULL,
    model_id text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text
);

ALTER TABLE public.agent_model_overrides
    ADD CONSTRAINT agent_model_overrides_pkey PRIMARY KEY (agent_name);

-- dsstar_app already has `GRANT ... ON ALL TABLES IN SCHEMA public` from db/init.sql, but
-- that grant only applies to tables that existed at the time it ran — new tables created
-- afterward (these) need it re-stated explicitly.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.users TO dsstar_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_prompts TO dsstar_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_model_overrides TO dsstar_app;
