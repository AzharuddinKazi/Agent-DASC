# DS-STAR Backend

FastAPI service that exposes the DS-STAR agent pipeline over HTTP. See the
[repo-level README](../README.md) for the overall architecture and a diagram of the agent
graph; this file covers backend-specific setup, structure, and the API surface.

## Layout

```
backend/
├── main.py                 FastAPI app: routes, task lifecycle, health checks
├── auth.py                 Bearer-token auth via Supabase (validates the JWT, returns the user)
├── db.py                   Supabase client (service-role key — used for all DB writes)
├── llm_router.py           Single gateway for all OpenRouter calls; tier→model mapping, timeouts
├── domain_pack.py          Reads/writes the currently active domain pack setting
├── knowledge.py            Ingests uploaded documents into the domain-pack knowledge base (RAG)
├── observability.py        Structured logging + optional Sentry error tracking setup
├── generate_synthetic_data.py  Generates example datasets for domain packs
├── agents/                 The LangGraph pipeline — one file per node (see below)
├── domain_packs/           Domain pack catalog + example packs (e.g. fraud/AML)
├── scripts/manual_e2e_smoke_test.py  Manual smoke test against a running stack
└── tests/                  pytest suite
```

## The agent graph (`agents/`)

`agents/graph.py` wires these nodes into the state machine described in the
[repo README](../README.md#how-it-works). `agents/state.py` defines `TaskState`, the single
dict every node reads and returns partial updates to — nodes never call each other directly.

| File | Node(s) | Responsibility |
|---|---|---|
| `analyzer.py` | `analyzer` | Describes each dataset in `data/`; entry point of every task |
| `question_generator.py` | `question_generator` | Report mode only: splits the query into sub-questions |
| `planner.py` | `planner` | Proposes the next plan step in plain English (max `max_rounds`) |
| `coder.py` | `coder` | Turns the current plan step into a Python script |
| `executor.py` | `executor` | Runs the script in the `dsstar-sandbox` container, captures stdout/exit code |
| `debugger.py` | `debugger` | Patches a failing script from its traceback (max 2 attempts) |
| `verifier.py` | `verifier` | Judges whether the output answers the query |
| `router_agent.py` | `router_agent` | Decides whether to add a plan step or backtrack |
| `finalizer.py` | `finalizer` | Writes `final_result`, marks the task `completed`/`failed` |
| `graph.py` | `sub_result_collector`, `gap_question_generator`, `human_review_gate`, `report_finalizer` | Report-mode bookkeeping: store each sub-answer, turn evaluator gaps into new sub-questions, park the task for an opt-in human refine-vs-finalize decision (`require_human_review`), store the final report |
| `writer.py` | `writer` | Report mode only: drafts the combined report from all sub-results, numbering and citing each one (`[N]`, alphabetic per refine round) |
| `report_evaluator.py` | `report_evaluator` | Report mode only: critiques the draft, lists gaps or approves it |
| `logger.py` | — | `log_event()` — every node calls this to append a timestamped entry to the task's `logs` in Supabase, which the frontend polls for the live pipeline timeline |
| `cancellation.py` | — | Cooperative Stop/Pause/Resume, checked at every node boundary by the `_cancellable()` wrapper `graph.py` applies to each node; also backs the human-review checkpoint's park/resume |
| `query_clarity.py` | — | Not a graph node — runs before a task is even submitted (`POST /api/v1/clarify_task`), asking the user to disambiguate a genuinely unclear query |

`agents/` also has several cross-cutting files with no dedicated graph node — `domain_knowledge.py`
(RAG retrieval shared by planner/coder/verifier), `prompt_safety.py` (labels untrusted content
before it's interpolated into a prompt), `error_sanitizer.py` (strips internals from
tracebacks before they're stored/served), `sandbox_security.py` (Docker hardening flags),
`script_repair.py` (fixes a specific known LLM code defect), `schemas.py` (Pydantic validation
of LLM JSON output), `json_sanitize.py` (NaN/Infinity → `null` before re-serializing), and
`code_fences.py` (strips a response's markdown code fence).

## API

All `/api/v1/*` routes except domain-pack downloads require `Authorization: Bearer <supabase-jwt>`.

| Method & path | Purpose |
|---|---|
| `GET /health` | Pings DB, Docker daemon, and OpenRouter in parallel; returns per-check latency and current pipeline concurrency. 503 if any check fails. |
| `POST /api/v1/clarify_task` | Body: `{query, task_type}`. Returns clarifying questions if the query is genuinely ambiguous, an empty list otherwise — called before submission, not a graph node. |
| `POST /api/v1/submit_task` | Body: `{query, formatting_guidelines?, task_type?: "qa"\|"report", require_human_review?}`. Inserts a `running` task row, kicks off the graph as a background task, returns immediately (202) with the `task_id`. Rate-limited (`SUBMIT_TASK_RATE_LIMIT`). |
| `GET /api/v1/get_tasks` | List the current user's tasks, newest first. |
| `GET /api/v1/get_task/{task_id}` | Full task row, including `logs` and (report mode) `sub_results`. |
| `POST /api/v1/tasks/{task_id}/stop` | Cooperatively interrupts a running task at the next node boundary, or stops it directly if parked at the human-review checkpoint. |
| `POST /api/v1/tasks/{task_id}/pause` | Same cooperative-interrupt mechanism as stop, but resumable. |
| `POST /api/v1/tasks/{task_id}/resume` | Resumes a paused task from its last LangGraph checkpoint. |
| `POST /api/v1/tasks/{task_id}/review` | Body: `{decision: "refine"\|"finalize"}`. Only valid while the task is `awaiting_review` (i.e. `require_human_review` was set and the evaluator judged the report insufficient). |
| `GET /api/v1/llm_speed_profile` | Current DB-backed speed profile (`"free"` or `"fast_paid"`, see LLM routing below). |
| `POST /api/v1/llm_speed_profile` | Body: `{profile: "free"\|"fast_paid"}`. Takes effect on the very next LLM call, no restart. |
| `GET /api/v1/domain_packs` | List available domain packs with the currently active one flagged. |
| `GET /api/v1/domain_packs/{pack_id}/config` | A pack's persona/classification/sub-question-dimension config. |
| `POST /api/v1/domain_packs/{pack_id}/activate` | Switch the active pack; takes effect immediately, no restart. |
| `POST /api/v1/domain_packs/deactivate` | Revert to the generic (no domain pack) default. |
| `GET /api/v1/domain_packs/{pack_id}/download` | Zip containing the pack's config as plain Python + its synthetic-data generator, for use outside this deployment. |
| `POST /api/v1/domain_packs/{pack_id}/documents` | Upload a document; ingested into the pack's RAG knowledge base in the background. |
| `GET /api/v1/domain_packs/{pack_id}/documents` | List uploaded documents and their ingestion status. |
| `DELETE /api/v1/domain_packs/{pack_id}/documents/{doc_id}` | Remove a document. |

Task submission is bounded by `MAX_CONCURRENT_PIPELINES` (default 10) — each run spins up a
2GB-capped sandbox container at the executor step, and unbounded concurrency was observed to
exhaust the Docker daemon/host memory around 15-20 simultaneous runs. Submissions above the
limit still get an immediate 202 and queue until a slot frees up.

Graph state is checkpointed to Postgres via `AsyncPostgresSaver` (keyed by `task_id` as the
LangGraph thread id), so an in-flight task survives a backend restart.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Docker daemon running (for the sandbox — see [repo README](../README.md#sandbox))
- A Supabase project — schema in [`../specs/database-schema.sql`](../specs/database-schema.sql)
- An OpenRouter API key ([openrouter.ai/keys](https://openrouter.ai/keys) — free tier covers
  every model this backend uses by default, no billing required)

## Setup

```bash
cp .env.example .env   # fill in the values below
uv sync
```

`.env` variables (see `.env.example` for the full annotated list):

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` — Supabase project + keys
- `SUPABASE_DB_URL` — direct Postgres connection string, used for the LangGraph checkpointer
- `OPENROUTER_API_KEY` — every LLM call (chat completions and domain-pack knowledge-base
  embeddings) goes through OpenRouter
- `DSSTAR` — absolute path to the repo root (analyzer/executor mount `$DSSTAR/data` into the
  sandbox container, resolved against the *host* filesystem)
- `OPENROUTER_MODEL_HIGH/MEDIUM/LOW`, `OPENROUTER_EMBED_MODEL` (optional) — override a tier's
  default `":free"` model if OpenRouter stops serving it
- `OPENROUTER_MODEL_HIGH_FAST/MEDIUM_FAST/LOW_FAST` (optional) — models used under the
  `"fast_paid"` speed profile (a live DB toggle, not set via env — see LLM routing below)
- `ALLOWED_ORIGINS` (optional) — comma-separated CORS origins
- `LOG_LEVEL` (optional) — see `observability.py`
- `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` (optional) — error tracking; unset disables it
  entirely, no external calls made
- `MAX_CONCURRENT_PIPELINES` (optional, default `10`)
- `SUBMIT_TASK_RATE_LIMIT`, `CLARIFY_TASK_RATE_LIMIT` (optional, default `20/minute`/`30/minute`)
  — per-bearer-token rate limits on the two endpoints that cost a real LLM call

## Running

```bash
# Build the sandbox image once — required before any task can execute
docker build -t dsstar-sandbox:latest ../sandbox

uv run uvicorn main:app --reload
```

Or run the full stack via Docker Compose — see [repo README](../README.md#option-a--docker-compose-backend--frontend-together).

## Testing

```bash
uv run pytest
```

Runs `agents/`, `main.py`, and state tests against mocked LLM/Supabase calls — no live
OpenRouter or Docker calls, so the count isn't reproduced here (it only goes up); see CI or
`pytest`'s own summary line for the current number. Logs and a JSON test report are written to
`tests/logs/` (gitignored).

For an end-to-end check against a real running stack (real LLM calls, real sandbox execution):

```bash
uv run python scripts/manual_e2e_smoke_test.py
```

## LLM routing

`llm_router.py` is the only place that calls an LLM — every call goes through OpenRouter. Each
agent is assigned a tier (`high`/`medium`/`low`) mapped to a model id, so reasoning-heavy nodes
(planner, coder, verifier) get a stronger model while cheap/structured tasks (routing,
classification) use a lighter one. Every call goes through a shared timeout and gets wrapped as
a `RuntimeError` on failure so nodes don't need to handle provider-specific exceptions.

Tier→model mapping is actually two full sets, selected by a live, DB-backed
`app_settings.llm_speed_profile` toggle (`GET`/`POST /api/v1/llm_speed_profile`) rather than a
deployment-time setting:

- **`"free"`** (default) — `":free"`-suffixed OpenRouter models, no billing required.
- **`"fast_paid"`** — small paid models chosen for throughput, for when the free tier's queue
  latency is the bottleneck rather than model quality.

Switching profiles applies to the very next LLM call, no restart needed, and always falls back
to `"free"` if never toggled or if the DB is unreachable. Both sets' defaults, and how to
override either, are documented in `.env.example`.

## Domain packs

A domain pack customizes the report persona, classification, and sub-question dimensions the
agents use — e.g. `domain_packs/fraud_aml_example.py` biases the pipeline toward fraud/AML
analysis framing. `domain_packs/catalog.py` lists available packs; the active one is stored in
Supabase (`app_settings`) and read by `domain_pack.py` on each task. `knowledge.py` handles
ingesting uploaded documents into a pack's RAG knowledge base so agents can ground answers in
uploaded reference material.
