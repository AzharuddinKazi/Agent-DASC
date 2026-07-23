-- DS-STAR Extended — PostgreSQL Schema
-- Ground truth data model. All API queries must filter by user_id where applicable.
-- Tables without user_id are shared org-wide (catalog, knowledge).

-- ============================================================
-- USERS (managed by Clerk / Keycloak — mirrored here for FK integrity)
-- ============================================================

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         TEXT NOT NULL UNIQUE,   -- Clerk/Keycloak user ID
    email               TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('admin', 'analyst')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DATA CATALOG (shared org-wide)
-- ============================================================

CREATE TABLE data_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,
    source_type         TEXT NOT NULL CHECK (source_type IN ('mysql', 'file')),
    connection_config   JSONB NOT NULL,         -- encrypted at app layer; host/db/user for mysql, path for file
    description         TEXT,
    last_scanned_at     TIMESTAMPTZ,
    created_by          UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE catalog_tables (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id      UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    table_name          TEXT NOT NULL,
    schema_name         TEXT,                   -- MySQL database name or NULL for files
    column_metadata     JSONB NOT NULL,         -- [{name, type, nullable, sample_values}]
    row_count_estimate  BIGINT,
    description         TEXT,
    scanned_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(data_source_id, schema_name, table_name)
);

-- ============================================================
-- KNOWLEDGE BASE (shared org-wide — feeds GraphRAG)
-- ============================================================

CREATE TABLE knowledge_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name           TEXT NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    mime_type           TEXT NOT NULL,
    graphrag_status     TEXT NOT NULL DEFAULT 'pending'
                            CHECK (graphrag_status IN ('pending', 'indexing', 'indexed', 'failed')),
    entity_count        INT,
    relationship_count  INT,
    community_count     INT,
    error_message       TEXT,
    uploaded_by         UUID NOT NULL REFERENCES users(id),
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indexed_at          TIMESTAMPTZ
);

CREATE TABLE knowledge_entities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    entity_name         TEXT NOT NULL,
    entity_type         TEXT NOT NULL,          -- e.g. CONCEPT, METRIC, TABLE, PROCESS
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE knowledge_communities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    community_title     TEXT NOT NULL,
    summary             TEXT NOT NULL,
    level               INT NOT NULL DEFAULT 0, -- GraphRAG hierarchy level
    entity_count        INT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ANALYSIS SESSIONS (private per user)
-- ============================================================

CREATE TABLE analysis_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    title               TEXT NOT NULL,          -- auto-generated from user query
    user_query          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'completed', 'failed', 'abandoned')),
    langgraph_thread_id TEXT UNIQUE,            -- LangGraph checkpointer thread ID
    data_source_ids     UUID[] NOT NULL DEFAULT '{}',
    is_shared           BOOLEAN NOT NULL DEFAULT FALSE,
    -- [LOCKED 2026-07-20] Set when this session was created via the force_exit round-2
    -- "start_fresh_session" action (specs/features/checkpoints-hitl.md). Lets the UI show
    -- "continued from session X" and lets the accumulated-hint chain be traced for
    -- debugging, instead of relying solely on the hints baked into user_query.
    forked_from_session_id UUID REFERENCES analysis_sessions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_analysis_sessions_forked_from ON analysis_sessions(forked_from_session_id);

CREATE INDEX idx_analysis_sessions_user_id ON analysis_sessions(user_id);
CREATE INDEX idx_analysis_sessions_status ON analysis_sessions(status);

-- ============================================================
-- AGENT STEPS (audit trail — one row per agent node execution)
-- ============================================================

CREATE TABLE agent_steps (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    -- [LOCKED 2026-07-20] Added 'subquestion_generator' and 'writer' — the original list
    -- omitted both DS-STAR+ agents, which meant their runs were never audit-logged.
    agent_name          TEXT NOT NULL CHECK (agent_name IN (
                            'analyzer', 'planner', 'coder', 'debugger',
                            'verifier', 'router', 'finalyzer',
                            'subquestion_generator', 'writer'
                        )),
    iteration           INT NOT NULL DEFAULT 1,
    input_state         JSONB,
    output_state        JSONB,
    generated_code      TEXT,                   -- Coder output, logged for audit
    execution_result    TEXT,                   -- Docker sandbox stdout/stderr
    duration_ms         INT,
    status              TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_steps_session_id ON agent_steps(session_id);

-- ============================================================
-- CHECKPOINTS (human-in-the-loop state)
-- ============================================================

-- [LOCKED 2026-07-20] checkpoint_type gained 'refine_round_review' (DSSTAR+ per-round
-- review, replaces the old "3 automatic refine rounds" default — see
-- specs/features/checkpoints-hitl.md). status/action were split: `status` is a small
-- universal set answering "is this checkpoint resolved", `action` records the specific
-- choice made, which varies per checkpoint type and would otherwise force the status enum
-- to grow every time a new checkpoint type is added.
CREATE TABLE checkpoints (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    checkpoint_type     TEXT NOT NULL CHECK (checkpoint_type IN (
                            'plan_approval',         -- CP1: after Planner_init
                            'force_exit',             -- max iterations reached (round 1 or 2 — see payload)
                            'result_confirmation',    -- CP2: after Verifier returns "Yes"
                            'refine_round_review',    -- after Writer_init / each Writer_refine (DSSTAR+ only)
                            'report_approval'         -- CP3: final save/export/discard
                        )),
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'resolved', 'abandoned')),
    -- The specific choice made when status = 'resolved'. NULL when status = 'abandoned'
    -- (abandon always sets status directly, not an action value) or 'pending'. Valid
    -- values depend on checkpoint_type — see the Action Routing table in
    -- specs/features/checkpoints-hitl.md:
    --   plan_approval:        approve | reject
    --   force_exit:           hint | start_fresh_session
    --   result_confirmation:  approve | hint
    --   refine_round_review:  refine_further | finalize
    --   report_approval:      approve
    action              TEXT,
    payload             JSONB NOT NULL,         -- plan steps / result / report URL depending on type
    user_hint           TEXT,                   -- populated when action = 'hint'
    responded_by        UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at        TIMESTAMPTZ
);

CREATE INDEX idx_checkpoints_session_id ON checkpoints(session_id);
CREATE INDEX idx_checkpoints_status ON checkpoints(status);

-- ============================================================
-- REPORTS (DSSTAR+ mode output)
-- ============================================================

CREATE TABLE reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id),
    title               TEXT NOT NULL,
    html_content        TEXT NOT NULL,
    html_file_path      TEXT,                   -- filesystem / GCS path
    pdf_file_path       TEXT,                   -- populated after PDF export
    is_shared           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pdf_generated_at    TIMESTAMPTZ
);

CREATE INDEX idx_reports_user_id ON reports(user_id);
CREATE INDEX idx_reports_session_id ON reports(session_id);

-- ============================================================
-- FULL-TEXT SEARCH (for history browser)
-- ============================================================

ALTER TABLE analysis_sessions
    ADD COLUMN search_vector TSVECTOR
        GENERATED ALWAYS AS (
            to_tsvector('english', title || ' ' || user_query)
        ) STORED;

CREATE INDEX idx_analysis_sessions_search ON analysis_sessions USING GIN(search_vector);
