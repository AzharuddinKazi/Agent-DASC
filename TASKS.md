# DS-STAR Task Tracker

## Status: live-app remediation (post production-readiness audit)

This tracker reflects the actual FastAPI + React app running in this repo. Earlier content in
this file described a from-scratch Next.js/Clerk/GraphRAG rebuild that was explored in a
separate environment and abandoned once this repo was confirmed canonical — that content no
longer matched reality and has been replaced; git history retains it if ever needed.

## Completed

- [x] DS-STAR paper pipeline (Analyzer → Planner → Coder → Executor → Verifier → Router →
      Finalizer) + DS-STAR+ report mode, LangGraph-based, Gemini via tiered LLM router
- [x] React/Vite/Tailwind/shadcn frontend, live end-to-end against Supabase
- [x] Dead-code cleanup (backend comments, 4 dead frontend files) — behavior-preserving only
- [x] Supabase connection-pooler fix (session-mode for LangGraph checkpointer)
- [x] White-labeling / domain-agnostic refactor — generic defaults + preserved fraud/AML
      example (`backend/domain_pack.py`, `frontend/src/config/brand.js`)
- [x] Domain Packs marketplace page — browse/download packs as zip
      (`backend/domain_packs/catalog.py`, `frontend/.../DomainPacks.jsx`)
- [x] Google-standard production readiness audit (published artifact, 41 findings, 9 P0
      blockers)
- [x] Audit remediation — **Auth**: Supabase Auth (self-serve signup + sign-in), per-user row
      scoping (`user_id` + RLS) on `tasks`
- [x] Audit remediation — **Health check**: `/health` now checks Supabase, Docker daemon,
      Gemini reachability; frontend sidebar shows live system status with a per-check tooltip
- [x] Domain pack knowledge base (RAG) + real in-app pack activation (DB-backed, no restart)
      — feeds the Planner subject-matter context from uploaded docs, scoped to whichever
      pack is active
- [x] Audit remediation — **Finalizer false-success bug**: a failed generated script now
      correctly sets `status: "failed"` instead of `"completed"` (`finalizer.py`), with a
      regression test (`tests/test_finalizer.py`). Also fixed 4 `test_main.py` tests that had
      silently started failing (401) since the auth work landed — never re-ran after adding
      auth. Suite is now 4 failing / 14 passing (was 8/9 before this pass, all remaining
      failures are the pre-existing `test_planner.py` live-DB-call issue below).
- [x] Audit remediation — **No timeout on Gemini calls**: every `generate_content` call now
      has a 120s bound (`llm_router.py`, matches the sandbox executor's own ceiling), embedding
      calls a 30s bound (`knowledge.py`). Timeouts raise `httpx.ConnectTimeout`, not
      `genai.errors.APIError` — broadened the except clause so they're still caught and wrapped
      cleanly instead of propagating unhandled. Two new regression tests in
      `tests/test_llm_router.py`.
- [x] Audit remediation — **CI**: `.github/workflows/ci.yml` (backend pytest + frontend
      build/lint) on every push and PR to `main`. Found and fixed something more urgent while
      wiring this up: `tests/test_end_to_end.py` had no `test_`-prefixed functions — it was a
      standalone script with `graph.invoke(...)` at module top level, and pytest *imports*
      every `test_*.py` file during collection, so **every pytest run in this repo, including
      many run manually this session, was silently executing a full live pipeline run**: real
      billed Gemini calls, real Docker sandbox execution, real writes to the production `tasks`
      table. Confirmed live — `pytest --collect-only` took 47s and hit the real API/DB before
      the fix, 1.1s after. Moved it to `backend/scripts/manual_e2e_smoke_test.py` behind
      `if __name__ == "__main__":`. Also fixed the same smaller pattern in
      `test_graph_build.py` (no live calls, but same "fake test file" anti-pattern), and two
      genuinely-live tests found while checking what a credential-free CI run would hit:
      `test_planner.py` (only mocked the LLM router, not `supabase` — this was the actual
      root cause of the `test_planner.py` failures/credential-leak-in-logs issue below, not
      just a symptom) and `test_main.py::test_health_check` (asserted 200 unconditionally, but
      `/health` legitimately returns 503 when a dependency is down). Suite is now **21 passed,
      0 failed**, runs in ~1.2s, needs zero real secrets — verified via `uv run pytest` with
      placeholder env vars, the exact command CI uses. Lint runs in CI but is non-blocking
      (`continue-on-error`) since its ~25 pre-existing errors are a separately-tracked item
      below, not something this task should silently gate on.
- [x] Audit remediation — **Deployable artifact**: `backend/Dockerfile`, `frontend/Dockerfile`
      (multi-stage, nginx), root `docker-compose.yml`. Two hardcoding fixes needed to make the
      artifact actually portable, not just containerized-but-still-localhost-only:
      `frontend/src/api.js`'s `API_BASE` and `main.py`'s CORS `allow_origins` are now both
      env-configurable (`VITE_API_BASE` build arg, `ALLOWED_ORIGINS` runtime env). Three real
      issues found and fixed while verifying live (not just "the containers start", the actual
      pipeline running end-to-end through them):
      1. `docker.io`'s Debian package only *Recommends* `docker-cli`, doesn't require it —
         `--no-install-recommends` silently produced a backend image with no `docker` binary.
      2. `analyzer.py` reads `$DSSTAR/data` directly in Python inside the backend process, not
         just via the sibling sandbox mount — the backend container needs that directory
         bind-mounted at the *same host path*, not just passed as an env var.
      3. `executor.py`/`analyzer.py` write the LLM-generated script via `tempfile`, then mount
         that path into the sibling sandbox container — but sibling-container mounts are always
         resolved against the *host* filesystem, and Python's default tempdir is private to the
         backend container. Fixed by pointing `TMPDIR` at a bind-mounted directory
         (`.dsstar-tmp/`), zero agent-code changes needed.
      Verified live: a real query through the fully containerized stack (frontend → backend →
      sibling sandbox container) completed correctly end-to-end, `/health` reports Docker
      reachable from inside the backend container, and the frontend image was rebuilt with two
      different `VITE_API_BASE` values to confirm it's genuinely configurable, not coincidence.
- [x] Audit remediation — **Structured logging + error tracking**: `backend/observability.py`,
      called once at `main.py` startup. All 24 real runtime `print()` calls (every `agents/*.py`
      file, `main.py`'s top-level exception handler) replaced with `logging.getLogger(__name__)`
      calls — JSON to stdout (timestamp, level, logger name, message, traceback when present),
      the standard pattern for a containerized app (matches the Docker deployment already
      shipped). Left `agents/logger.py`'s `log_event()` untouched — that's a distinct concern,
      user-facing pipeline *progress* stored in `tasks.logs` and polled by the frontend, not
      engineering/operational logging.

      Error tracking (Sentry) built and fully wired — FastAPI integration, plus an explicit
      `sentry_sdk.capture_exception()` in `run_graph`'s except block since that runs as a
      background task outside the request/response cycle the FastAPI integration instruments —
      but gated entirely on a `SENTRY_DSN` env var. Unset by default: verified live that with
      no DSN, `sentry_sdk.get_client().is_active()` is `False` and nothing changes; with a fake
      DSN set, the client activates and startup doesn't crash. Ships today with zero blocking on
      creating a Sentry account — flip it on whenever one exists by setting the env var, no code
      change needed. New `backend/.env.example` documents every env var the backend reads,
      including the two new optional ones (`SENTRY_DSN`, `LOG_LEVEL`).
- [x] Audit remediation — **Concurrency limit**: `main.py` gets a module-level
      `asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)` (env-configurable, default `10`, leaving
      headroom under the audit's own traced ~15-20 concurrent-execution failure threshold),
      wrapping `run_graph`'s actual pipeline execution — not the whole function, so DB cleanup
      writes never contend for a slot. Went with a semaphore over a task queue
      (Celery/RQ/arq) — the roadmap named both as acceptable, and a queue needs a new broker
      (Redis) for a problem this solves in-process. Two small additions so queuing is visible,
      not just bounded (a bare semaphore reproduces the audit's own "shows running with no
      signal it's actually queued" complaint in miniature): a queued task gets a `log_event`
      entry ("Queued — waiting for an available worker slot") the moment it starts waiting —
      reuses the exact `tasks.logs` mechanism the frontend already polls, so it's visible with
      zero frontend changes — and `/health` gained a `concurrency: {active, max}` field.
      Verified live: forced `MAX_CONCURRENT_PIPELINES=1`, submitted two tasks back to back,
      confirmed `/health` showed `active: 1` while the first ran, the second's log timeline
      showed the queued message, and `active` correctly cycled 0 → 1 → 1 (handoff) → 0 as both
      completed in sequence rather than in parallel.
- [x] DS-STAR+ report citations: the Writer now numbers each sub-analysis and cites it
      inline (`[N]`, e.g. "...8.3% [2]."), matching the paper's citation mechanism that this
      repo's report pipeline never implemented. The reference list itself (`report.sources`)
      is computed server-side from `sub_questions`/`sub_results` in `writer.py`, not trusted
      to the LLM — the model only emits the `[N]` markers, so numbering is always correct
      even if the model over/under-cites. Frontend (`ReportView.jsx`) renders `[N]` as
      clickable superscript badges in the executive summary, section bodies/key_stats, and
      conclusions; clicking one auto-expands the "Sources" section and scrolls to the
      matching sub-analysis. Falls back to numbering `task.sub_results` by iteration order
      for reports generated before this change (no `report.sources` present). Verified live
      end-to-end against a real report run (not just the 3 new `test_writer.py` tests).
- [x] DS-STAR+ report pipeline hardening + task controls (PR #15,
      `feat/report-hardening-and-task-controls`) — large session, summarized:
      - **Real bugs found and fixed, all verified live against real data**: `question_generator`
        silently producing 0 sub-questions on malformed LLM JSON (bumped tier + retry);
        `writer` output breaking the entire frontend render on unescaped `\$` in currency
        figures (prompt fix + repair fallback); a genuine sign-inversion bug where DE-SynPUF
        chronic-condition flags were summed raw instead of recoded, inverting a regression
        coefficient's sign in a regulatory-facing report (root-caused to domain-knowledge
        retrieval missing the fact for compound questions); a fence-stripping bug
        (`split("\n")[1:-1]`) independently duplicated across 4 agent files, consolidated into
        `agents/code_fences.py`.
      - **Hybrid retrieval** (`agents/domain_knowledge.py`): column-aware, wildcard-expanding
        grounded retrieval for planner/coder/verifier, dense + Postgres full-text search fused
        via reciprocal rank fusion for column-shaped queries
        (`migrations/2026-07-29_domain_pack_chunks_fts.sql`).
      - **Pre-analysis clarifying questions** (`agents/query_clarity.py` +
        `ClarifyingQuestionsModal.jsx`) — popup before submission/follow-up when a query is
        genuinely ambiguous, silent skip otherwise. Two real bugs found via this feature: the
        endpoint blocked the whole server's event loop on every call (sync HTTP inside
        `async def`, fixed via `run_in_executor`), and an 8s client timeout was cutting off
        genuinely-slow-not-wrong LLM responses (raised to 15s + added a distinct "Checking…"
        button state so the wait never reads as stuck).
      - **Stop/Pause/Resume task controls** (`agents/cancellation.py`) — cooperative
        interruption checked at every graph-node boundary, polled during in-flight Docker
        execution (force-kills the container rather than waiting out the 120s timeout). Found
        and fixed the actual root cause blocking this and the "Human-in-the-loop checkpoints"
        item below: the `AsyncPostgresSaver` checkpointer was opened, set up, and closed
        during app startup, *before ever serving a request*, and `build_graph()` was never
        even given a reference to it — checkpointing had never actually worked. Resume
        semantics (restart the interrupted step, continue from the last real checkpoint)
        verified empirically against LangGraph's actual behavior, not assumed.
      - **Insight (QA) dashboard redesign** (`ReportSections.jsx`) — audited against a
        real-analyst-workflow standard (claim → evidence → trust → action). Promoted the
        actual answer to a real headline (was 3rd on the page, below a stat grid and a dark
        Key Findings card); merged the chart and its backing table into one "Evidence" card;
        removed a "Risk Highlights" card that guessed a business framing from column-name
        keywords on every query regardless of fit; replaced a fabricated client-side
        token/cost estimate with real provenance (`finalizer.py` now injects `debug_attempts`
        and `files_used` into its own JSON output server-side, same pattern as writer.py's
        server-built sources list).
      - Test count: 94 → 196 backend tests, all passing against CI's actual dummy-credential
        environment (fully mocked, no live network, sub-second run).
- [x] **Fully local LLM stack via Ollama** (2026-08-22) — replaced OpenRouter (chat +
      embeddings) with a local Ollama server (`http://localhost:11434/v1`, OpenAI-compatible,
      needs no code changes beyond env vars + one router extension). Verified zero remaining
      calls to `openrouter.ai` anywhere in the codebase.
      - **Model-to-agent mapping** (RTX 5060 Ti, 16GB VRAM): `qwen2.5-coder:14b` for
        `coder`/`debugger`/**`finalizer`** (finalizer generates and executes real Python
        despite its tier comment calling it "templated formatting" — discovered by
        live-testing: llama3.1:8b burned both its debug attempts on plain syntax errors and
        failed the task outright); `qwen3:14b` for `planner`/`verifier`/`writer`/
        `question_generator`; `llama3.1:8b` for `router`/`query_clarity`/`report_evaluator`;
        `llama3.2:3b` for `analyzer`/`sub_result_collector`. Implemented as
        `LLMRouter._AGENT_OVERRIDES` in `llm_router.py` (checked before the tier lookup) —
        `OPENROUTER_MODEL_CODER` env var, applies to all three code-gen agents.
      - **Context length**: baked `PARAMETER num_ctx` into 4 custom Ollama tags
        (`dsstar-coder:16k`, `dsstar-high:16k` both 16384; `dsstar-medium:8k`, `dsstar-low:8k`
        both 8192) via Modelfiles, because the plain OpenAI-compat `/chat/completions`
        endpoint accepts no `num_ctx` override and an uncapped default was measured spilling
        5% onto CPU at ~32k context (15GB VRAM, 1GB free — vs. 11GB/3.9GB free at the capped
        16k). Live-measured, not estimated.
      - **Embeddings**: `nomic-embed-text` (768 dims, ~274MB) via the same local endpoint,
        replacing `nvidia/nemotron-3-embed-1b:free` (2048 dims). Migrated
        `domain_pack_chunks.embedding` from `vector(2048)` → `vector(768)`
        (`migrations/2026-08-22_domain_pack_chunks_local_embeddings.sql` — table was empty,
        clean ALTER, no re-embedding needed). Verified live: coexists in VRAM alongside a
        loaded 14B chat model with no eviction (11.3GB used, 3.5GB free), full round-trip
        tested (embed → insert → `match_domain_pack_chunks` similarity search → real 0.84
        score → cleanup).
      - **Also fixed along the way** (both real bugs surfaced by actually running tasks
        against the new setup, not theoretical): `/health`'s LLM check was hardcoded to
        OpenRouter's proprietary `/key` endpoint (404s on Ollama) — switched to the standard
        `/models` endpoint both providers implement (`main.py::_ping_llm`). A stuck Supabase
        Postgres connection left one task's status frozen at "running" after it had actually
        finished (confirmed via `ss` showing a stalled TCP send queue) — unrelated to Ollama,
        manually resolved; flagged as a data point for the local-Postgres migration below
        (this class of flakiness disappears once Postgres is `localhost`).
      - `MAX_CONCURRENT_PIPELINES` dropped from 10 → 1 (one GPU serves one inference at a
        time), `LLM_TIMEOUT_S` raised from 120 → 600 (a local 14B model on one consumer GPU
        can take minutes for an 8k-token completion — measured, not hypothetical — vs. a
        hosted cluster's seconds).
      - **Known gap, not yet done**: `OPENROUTER_API_KEY`/`OPENROUTER_BASE_URL`/
        `OPENROUTER_MODEL_*` names are now purely cosmetic legacy (zero requests reach
        OpenRouter — verified) — a provider-neutral rename (`LLM_BASE_URL` etc.) was offered
        and declined for now, not forgotten.
      - Test suite: 315/317 pass. The 2 failures
        (`test_llm_router.py::test_free_models_require_no_billing`,
        `test_main.py::test_get_llm_speed_profile_returns_current_profile_and_models`) assert
        OpenRouter's `":free"` naming convention on the *default* (env-unset) model ids —
        they now correctly see this machine's local Ollama tags via the shared `.env` instead.
        Not a regression; only fails in this environment because `.env` overrides the
        defaults these two tests inspect.

- [x] **Supabase → local Docker Postgres migration** (2026-08-22, same day as scoping —
      picked up immediately in the session that scoped it). Goal achieved: the whole app
      runs fully offline on one machine — no OpenRouter (already done, see above) and no
      hosted Supabase for anything on the request path. Followed the ordered steps below
      almost exactly, with two corrections the plan got wrong (both found live, not
      theoretical) and one gap left open — see "What the plan got wrong" and "Remaining"
      at the end of this entry.
      - `db/init.sql` — sanitized schema dump (via `docker run --network host postgres:17
        pg_dump ...` against the live Supabase project; `--network host` was needed, plain
        bridge networking couldn't resolve the pooler's IPv6 address). Table bodies moved
        before the 3 SQL functions that reference them (`check_function_bodies` isn't off
        by default the way `pg_dump`'s own preamble sets it — functions failed to create
        against empty tables otherwise). `checkpoint_*` tables, RLS/policies, the two
        `auth.users` FKs, and `supabase_vault` dropped per plan; `pg_stat_statements` also
        dropped (needs `shared_preload_libraries` set at server start, not just `CREATE
        EXTENSION` — not worth the complication for an unused stats extension).
      - `docker-compose.yml` — `postgres` (pgvector/pgvector:pg17, published on 5432),
        `postgrest`, and a `postgrest-gateway` (nginx, see below) added; `backend` now
        depends on the gateway. `postgres`/`postgrest`/`postgrest-gateway` all published to
        the host (5432/3001/3002) — not just for the docker-compose stack itself, but so a
        host-side `uv run uvicorn` dev session (the documented normal dev workflow) can
        reach them too.
      - `backend/auth.py` — real Supabase Auth removed, single fixed local user
        (`00000000-0000-0000-0000-000000000001`, `local@dsstar.local`) exported as
        `LOCAL_USER`. `get_current_user`/`get_current_admin` collapse to stubs; every
        existing `Depends(get_current_user)`/`.id`/`.email` call site in `main.py` keeps
        working unchanged. `main.py`'s Supabase-Auth-Admin-backed user-management endpoints
        (`/admin/users`, `/ban`, `/unban`, `/admin/admins`) had no local equivalent (GoTrue
        is gone) — rewritten to report the single-user reality honestly (list returns just
        `LOCAL_USER`; ban/unban now 501; admins list is always `[LOCAL_USER.email]`) rather
        than crash or silently no-op.
      - Frontend — `useAuth.js` rewritten as the same kind of local-user stub (mirrors
        `auth.py`) rather than deleted, since 3 files consumed it
        (`App.jsx`/`Sidebar.jsx`/`admin/AdminApp.jsx`, one more than the plan's "both
        places" assumed). `Login.jsx`/`AdminLogin.jsx` deleted (now unreachable — `user` is
        always truthy), `lib/supabaseClient.js` deleted, `@supabase/supabase-js` uninstalled,
        `docker-compose.yml`'s `VITE_SUPABASE_*` build args removed. Frontend build verified
        clean.
      - Backend test suite updated for the auth removal (not called out explicitly in the
        original plan, but necessary): 16 `test_*_requires_auth`/`test_*_requires_admin`
        tests deleted across `test_main.py` and the 4 admin-panel test files — they pinned
        an unauthenticated/non-admin-rejection invariant that auth removal deliberately
        eliminates. `test_auth.py` and `test_admin_users.py` rewritten for the new stub
        behavior. Suite: 299 passed, same 2 pre-existing failures as before this work
        (the local-Ollama-model-naming ones from the same-day earlier session, unrelated).
      - **Verified live, step 6 of the plan**: `/health` all-green (database/docker/llm
        all `ok`) on a host-side `uv run uvicorn` run; a real QA task submitted through
        `/api/v1/submit_task` ran the full pipeline (analyzer → planner → coder → verifier,
        3 rounds) against real data in `data/`, real local Ollama inference, and the real
        Docker sandbox executor, and reached `status: completed` with `user_id` correctly
        resolved to `LOCAL_USER`'s fixed uuid in local Postgres. `checkpoint_*` tables
        confirmed auto-created by `langgraph-checkpoint-postgres` on first connect (no
        manual schema needed, per plan). Both RAG SQL functions
        (`match_domain_pack_chunks`, `match_domain_pack_chunks_fts`) verified directly
        against a scratch chunk insert/query/cleanup — dense vector similarity and
        Postgres full-text search both return correctly.

      **What the plan got wrong** (corrected live, not just theoretical risk):
      1. "Leave `PGRST_JWT_SECRET` unset" does **not** work — `supabase-py` always sends an
         `Authorization: Bearer <key>` header, and PostgREST 500s (`PGRST300`, "Server
         lacks JWT secret") on *any* request carrying that header if no secret is
         configured, regardless of `PGRST_DB_ANON_ROLE`. Fixed instead with a real
         `PGRST_JWT_SECRET` (docker-compose.yml) and `SUPABASE_ANON_KEY`/`SERVICE_KEY` set
         to JWTs signed with it carrying `{"role": "dsstar_app"}` — every request still
         resolves to the one app role, just via a valid JWT instead of an absent secret.
      2. `supabase-py`'s REST client hardcodes `<SUPABASE_URL>/rest/v1/...` (it's built for
         Supabase's own Kong gateway, which adds that prefix in front of a real PostgREST
         that itself serves tables at the root) — plain `postgrest/postgrest` has no prefix
         option, so `backend/.env`'s `SUPABASE_URL` couldn't point straight at it. Fixed
         with `postgrest-gateway` (nginx, `postgrest-gateway/nginx.conf`), a one-route
         rewrite (`/rest/v1/(.*)` → `/$1`) sitting between the backend and `postgrest`.

      **Fixed same-day, after the fact**: the Docker→host Ollama gap above was confirmed
      to be exactly that — `ufw` enabled, an allow rule for `sshd` (22) but none for Ollama
      (11434), so `INPUT`-chain filtering silently dropped the container's connection
      (timeout, not refused) while Docker's own container-published ports (5432, 3001,
      etc.) were unaffected since those bypass `ufw`'s normal filtering via Docker's own
      NAT rules. Fix (run by the user, needs sudo — this session doesn't have it):
      `sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp` (scoped to Docker's
      whole private range, not just the one subnet in play today, so a future
      `docker compose` project's new `172.x.0.0/16` network doesn't need this redone) +
      `sudo ufw reload`. Verified live afterward: `docker exec agent-dasc-backend-1 ...`
      reaches `http://host.docker.internal:11434/api/tags` (200), and the fully
      containerized backend's `/health` is now all-green (`database`/`docker`/`llm` all
      `ok`) with zero host-side workaround — `docker compose up -d` alone is sufficient now.

      **Second bug found and fixed same-day, also containerized-deployment-only**: every
      script execution failed — `Exit code: 2`, `python3: can't open file
      '/workspace/scripts/step.py': [Errno 13] Permission denied` — through the Executor,
      the Debugger's retry, and the Finalizer alike. Root cause: `tempfile.NamedTemporaryFile`
      (`agents/executor.py`, `agents/analyzer.py`) always creates its file mode `0600`
      regardless of umask, owned by whatever UID the writing process runs as. `backend/
      Dockerfile` has no `USER`, so the backend runs as root when containerized; `sandbox/
      Dockerfile`'s `dsstar-sandbox` image runs as `USER app` (UID 1000) — so the sandbox
      container could never read its own read-only-mounted script. UID-dependent, not a
      regression from this session's other changes: it silently didn't matter whenever the
      backend happened to run on the host as a user whose UID numerically matched the
      sandbox's UID 1000, which is why earlier "verified live end-to-end" sessions (see the
      "Deployable artifact" entry above) never hit it — those ran the backend on the host,
      not containerized. Running the backend containerized (this session's new default
      path) made it deterministic. Fixed with `os.chmod(script_path, 0o644)` right after
      writing, in both files — the script is mounted `:ro` into the sandbox regardless, and
      its content is just the LLM's own generated analysis code, nothing sensitive. Two new
      regression tests (`test_execute_script_makes_temp_script_world_readable`,
      `test_analyze_file_makes_temp_script_world_readable`) assert the real file's mode on
      disk, not a mocked chmod call. Verified live: resubmitted a QA task through the fully
      containerized stack, both script executions came back `Exit code: 0`, task completed
      with a real result. Full suite: 301 passed (299 + the 2 new tests), same 2
      pre-existing unrelated failures as before.

      **Third bug found and fixed same-day, caught by the user testing Insight mode live
      from the actual UI** (not curl): the answer computed correctly but the frontend
      showed "Could not parse structured output — see raw result below" instead of the
      formatted card/chart. `agents/finalizer.py` already caught JSON parse failures but
      just silently passed through the broken output. Two distinct near-miss patterns,
      both fixed the same way `writer.py` handles its own near-miss-JSON problem
      (`_strip_invalid_escapes`) — repair-and-reparse rather than give up:
      1. The model sometimes prints a Python dict (`print(result_dict)`, single-quoted
         keys) instead of calling `json.dumps` — fixed via `ast.literal_eval` (parses
         exactly the literal syntax a Python repr produces, never arbitrary code).
      2. One step further: the model leaves its exploratory prints (column listings,
         `df.head()`, a `[5 rows x 17 columns]` pandas summary line) before the actual
         answer object, so neither `json.loads` nor the repr-repair can parse the whole
         mixed string as one literal — fixed by extracting from the last `{` onward (the
         answer object is always the final print) and trying both parsers on just that.
      Two new regression tests capture the exact live-observed shapes
      (`test_finalizer_repairs_python_repr_output_into_json`,
      `test_finalizer_extracts_trailing_object_when_script_prints_debug_output_first`).
      Verified live twice: once via the actual browser UI (Insight mode, 3 rounds,
      correct answer, still hit the raw-text fallback — this bug), then again via the
      API after the fix (`final_result` now parses as clean JSON with the real answer).
      Full suite: 303 passed (301 + 2 new), same 2 pre-existing unrelated failures.

      **Remaining** (not done in this pass):
      - Only a QA task was smoke-tested end-to-end; report-mode (DS-STAR+) and
        domain-pack-document-upload-through-the-actual-endpoint (as opposed to the direct
        SQL RAG check above) weren't separately exercised.
      - Step 7 (decide whether to pause/decommission the hosted Supabase project) not
        done — by design, per the plan's own "don't do this preemptively" note, and
        because report-mode/domain-pack upload aren't smoke-tested yet either. The hosted
        project, and a full credentials backup (`backend/.env.supabase-backup`, gitignored),
        are both still intact as the fallback.

- [x] **Reverted local Ollama stack back to OpenRouter** (2026-08-23) — the 2026-08-22
      "Fully local LLM stack via Ollama" entry above is now history, not the live config;
      kept rather than rewritten since it documents real work (Modelfiles, VRAM
      measurements) that's still true of *that setup*, just not this deployment anymore.
      - `backend/.env`: restored the real `OPENROUTER_API_KEY`, dropped the
        `OPENROUTER_BASE_URL`/`OPENROUTER_MODEL_*`/`OPENROUTER_EMBED_MODEL` local-Ollama
        overrides (llm_router.py's/knowledge.py's hardcoded free-tier defaults apply
        again), dropped `LLM_TIMEOUT_S` back to its 120s default, restored
        `MAX_CONCURRENT_PIPELINES` 1 → 10 (no longer bottlenecked on one local GPU).
      - `docker-compose.yml`: removed the `host.docker.internal` extra_host and
        `OPENROUTER_BASE_URL` override that existed only to route the backend container to
        the host's Ollama server.
      - `domain_pack_chunks.embedding`: `vector(768)` (local nomic-embed-text) → back to
        `vector(2048)` (OpenRouter's nvidia/nemotron-3-embed-1b:free) — see
        `migrations/2026-08-23_domain_pack_chunks_openrouter_embeddings.sql`. Table was
        empty, safe in-place ALTER, no re-ingestion needed. `db/init.sql` updated to match
        for fresh installs.
      - As a side effect, confirmed why `test_free_models_require_no_billing` and
        `test_get_llm_speed_profile_returns_current_profile_and_models` kept showing up as
        "pre-existing failures" all through the Ollama period: both assert OpenRouter's
        `:free` naming on the *default* model ids, and the local `.env` was overriding
        those defaults with Ollama tag names. Full suite is 349/349 now that it isn't.
      - Live-verified: `/health`'s `llm` check hit the real OpenRouter endpoint
        successfully (86ms) with the restored key.
      - Left alone, deliberately: `llm_router.py`/`knowledge.py`'s local-Ollama support
        code and docstrings (still-valid optional capability, not dead config), and
        `main.py`'s `_local_ollama_tags` best-effort admin-panel helper (already
        degrades to `[]` gracefully against a non-Ollama endpoint like OpenRouter).

- [x] **Researched and reassigned free/paid model picks; surfaced the speed-profile
      toggle in the admin UI; fixed two real bugs found via live testing** (2026-08-23).
      - **Admin UI**: Models panel's Speed Profile was previously read-only display
        text — the actual toggle only existed as a raw `curl` command in `.env`
        comments. Added a real Free/Paid selector (draft/stage/Save pattern, same as
        Feature Flags — a switch to paid billed models isn't instant-on-click) plus a
        billing warning shown only when staging a switch *to* paid.
      - **Free tier**: `high` (and new `coder` pseudo-tier, see below) raised from
        `nvidia/nemotron-3-super-120b-a12b:free` to `nvidia/nemotron-3-ultra-550b-a55b:free`
        — 550B MoE, 48.2 Artificial Analysis Intelligence Index, 71.9% SWE-bench
        Verified (researched via OpenRouter's live `/api/v1/models` + web search, not
        training-data knowledge — this and every model below postdates this session's
        knowledge cutoff).
      - **Paid tier**: replaced the previous flat `meta-llama/llama-3.1-8b-instruct:nitro`
        across every tier — an 8B model doing planner/verifier/writer work, actually
        *weaker* than the free tier's model it nominally upgraded from — with real
        per-tier picks: `high` → `qwen/qwen3-235b-a22b-2507` (~$0.09/$0.55 per M),
        `medium` → `google/gemini-2.5-flash-lite` (~$0.10/$0.40 per M, built for
        reliable structured output), `coder` → `qwen/qwen3-coder-next` (~$0.12/$0.80 per
        M, 70.6% SWE-bench Verified). `low` stays on the free model, unchanged design
        intent (not this profile's speed bottleneck).
      - **New "coder" pseudo-tier**: `coder`/`debugger`/`finalizer` previously fell
        through to the generic "high" tier model unless the legacy `OPENROUTER_MODEL_CODER`
        env var was manually set (never was) — despite `llm_router.py`'s own docstring
        already explaining they need a code-specialized model, not a generalist one.
        `_FREE_MODELS`/`_FAST_PAID_MODELS` each gained a `coder` key
        (`OPENROUTER_MODEL_CODER_FREE`/`_FAST` env overrides), and
        `LLMRouter.complete()`/`admin_list_models` both route those three agents to it
        instead of their nominal `AGENT_TIERS` entry. The old `OPENROUTER_MODEL_CODER`
        (no suffix) still works as a higher-priority manual pin, e.g. for a local Ollama
        tag, unaffected by the speed-profile toggle.
      - **Live-verified**, both profiles, full pipeline against the real 250k-row
        `transactions_data.csv`: free profile and paid profile each independently
        produced numbers matching hand-computed ground truth exactly (paid ran in
        ~15-20s vs. free's ~45-55s). One paid run and one free run answered a
        genuinely ambiguous "flagged transactions" phrasing two different
        self-consistent ways (`aml_category != 'Normal'` vs. `str_filed == True`) —
        checked both against raw data, both correct under their own reading; not a
        model-quality issue.
      - **Real bug #1 found + fixed**: `qwen/qwen3-coder-next` (the new paid coder
        model) leaked a literal `[/python]` closing tag into one generated script,
        becoming a real `SyntaxError` and burning a debug attempt — `strip_code_fences`
        only handled markdown triple-backtick fences. Root cause: `DEBUGGER_PROMPT`
        itself wraps code in `[python]...[/python]` tags when showing the model its own
        broken code to fix, and this model apparently sometimes echoes that convention
        back. Fixed: `strip_code_fences` now strips `[python]`/`[/python]` tags too
        (case-insensitive), independent of and in addition to markdown fence handling.
      - **Real bug #2 found + fixed**: a finalizer script that exits 0 but prints
        nothing was previously reported as a `"completed"` task with an empty
        `final_result` — no error, no retry, just a blank answer the frontend would
        render with no explanation. Hit live with the new free `coder` model on one run
        (self-recovered on a later unrelated run — likely one-off model non-determinism,
        can't be conclusively attributed to the model swap from one occurrence). Fixed:
        blank-stdout-despite-exit-0 now triggers the same self-debug retry loop as a
        nonzero exit (with a real "you forgot to print the answer" message instead of an
        empty `stderr`), and is reported as `status: "failed"` with an honest error
        message if still blank after exhausting retries, never silently `"completed"`.
      - Test suite: 358/358 (7 new tests: 2 for the coder pseudo-tier's routing/admin
        display, 3 for the `[python]` tag stripping, 2 for the blank-output retry/fail
        path), rebuilt and re-verified live after each fix.

- [x] **Real "Export DOCX" for Research mode reports, plus a real bug it surfaced**
      (2026-08-23). The only prior "export" for a report was ReportView.jsx's `window.print()`
      button — the browser's own print dialog, not a generated file at all, unusable
      from any caller other than a human clicking it in that exact browser.
      - `backend/report_export.py` (new): converts the writer's report JSON (see
        writer.py's `_PROMPT_TAIL` for the schema) into a real `.docx` via `python-docx`
        (already a dependency — knowledge.py already used it the other direction, for
        reading uploaded `.docx` files). Strips the writer's markdown subset
        (`**bold**`, `` `code` ``) into real run formatting, splits multi-paragraph
        section bodies, renders `risk_matrix` as a real table with dynamically-named
        dimension columns (the writer picks 2-4 per report, not a fixed schema), and
        lists `sources` with their citation ids.
      - New endpoint `GET /api/v1/get_task/{task_id}/export.docx` — same ownership
        check as `get_task`, 422 for a non-report task or a report whose JSON didn't
        parse, 409 if still running, else a real streamed `.docx` download.
      - Frontend: `ReportView.jsx` gets a real "Export DOCX" button next to "Export
        PDF" — fetched as an authenticated blob (`api.js`'s `exportReportDocx`, needs
        the session cookie, so a plain `<a href>` at the API origin wasn't an option)
        and downloaded via the same synthetic-anchor pattern `ReportSections.jsx`'s
        CSV export already used.
      - Test suite: 17 new tests (12 for `report_export.py`'s document-building logic
        against synthetic reports, 5 for the endpoint's auth/ownership/validation) —
        375/375 total before the bug below, 378/378 after.
      - **Real bug found + fixed, live**: a real end-to-end report generation produced
        JSON truncated mid-sentence with no closing braces at all — traced to
        `llm_router.py` never sending `max_tokens` in the OpenRouter request body, so
        every call rode on the provider's own unstated default completion cap. Harmless
        for short/structured agent outputs, but writer.py explicitly asks for a
        "genuinely comprehensive... do not artificially limit length" report — exactly
        the shape most likely to hit an unstated cap. Same bug independently breaks the
        existing on-screen ReportView render and "Export PDF", not just the new
        endpoint — pre-existing, not introduced by this feature, just surfaced by
        actually generating a real report to test the export against. Fixed: explicit
        `LLM_MAX_TOKENS` (default 8000, env-overridable) sent on every call; a
        `finish_reason: "length"` response now logs a real task-log warning instead of
        silently shipping truncated JSON with no indication why it won't parse. Not
        retried automatically (a repeat attempt would likely hit the same ceiling
        again).
      - **Live-verified end-to-end after the fix**: a real 6-sub-question report
        against the actual 250k-row dataset produced valid, complete JSON (6 sections,
        a 4-row risk matrix, 3 recommendations, 6 sources), and the export endpoint
        turned it into a real, correctly-formatted 55KB `.docx` — confirmed by reading
        it back with `python-docx`: title, executive summary, 6 headed sections with
        markdown properly stripped and key-stat callouts, a real table with the
        report's own 3 dynamic risk dimensions, conclusions, bulleted recommendations.
      - Hit two long delays chasing this live proof that turned out to be nothing —
        both eventually completed successfully (~80-90s for the writer step alone,
        legitimately long for a multi-thousand-word synthesis, not actually stuck);
        worth knowing free/paid report-mode generation can look stalled for a couple of
        minutes before finishing, not necessarily a sign anything is wrong.

## In progress — Google OAuth login + Admin Control Panel
## (implemented 2026-08-23, on branch `feat/google-oauth-admin-panel`, still uncommitted)

Requested by the user right after using the app auth-free for a few hours post-migration —
supersedes the "Auth: drop entirely" decision above, for a demo to the user's department
head. Two parts: (1) real Google sign-in replacing the single-local-user stub, (2) a proper
admin control panel beyond the prior feature-flag/task/domain-pack panels — prompt editing
per agent, per-agent model override, and data visibility. User's own decisions: open
sign-up (any Google account), admin = `kaziazhar04@gmail.com` only.

**Re-verified live 2026-08-25** (re-scanned the running stack, not re-run from scratch —
`docker compose ps` showed the same containers up 14h). `backend/.env`/`frontend/.env` both
have real (non-placeholder) `GOOGLE_CLIENT_ID`/`VITE_GOOGLE_CLIENT_ID` values, and the
`2026-08-23_users_and_admin_config.sql` migration is applied (`users`, `agent_prompts`,
`agent_model_overrides`, `app_settings` all present in local Postgres). Backend suite now
378/378 (up from 338 on 2026-08-23 — more work landed since that entry was last edited,
not reflected here until now), `npm run build` clean.

- [x] Real Google sign-in round-trip works end-to-end — confirmed via a real `users` row:
      `kaziazhar04@gmail.com`, `auth_provider='google'`, real `google_sub` set, name "Azhar
      Kazi" pulled from the real Google profile, `last_sign_in_at` populated.
- [x] A task submitted under the real account has `tasks.user_id` resolving to that
      account's row — 6 of 15 tasks in the DB belong to `31c39681-...` (that user's id),
      not the old fixed local uuid (`00000000-...`, only present on tasks from before this
      branch).
- [x] Admin: `kaziazhar04@gmail.com`'s user row has `is_admin=true` (set via
      `ADMIN_EMAILS` on first sign-in). Didn't re-test the "Not authorized" screen for a
      second non-admin account this pass — no second real Google account signed in during
      this scan (4 other users in the DB are `auth_provider='guest'`, not Google, see
      below).
- [ ] Prompt edits actually changing pipeline behavior — **not yet exercised**:
      `agent_prompts` table is empty (no rows), so no admin prompt edit has been saved yet.
- [ ] Model override actually routing the LLM call — **not yet exercised**:
      `agent_model_overrides` table is empty too.
- [ ] Ban a second real Google test account and confirm it's locked out — **not yet
      exercised**: no user in the DB currently has `is_banned=true`. The mechanism itself
      is real (`POST /admin/users/{id}/ban` sets `is_banned`, and `main.py` re-checks
      `is_banned` from the DB on every request per its own comment, not just at login) —
      just hasn't been fired against a live second account.
- [ ] Data panel shows real `data/` files and real cross-pack documents — endpoint
      (`GET /api/v1/admin/data-files`) exists but wasn't confirmed hit live this pass.
- [x] `npm run build` clean, `uv run pytest` clean — re-confirmed 2026-08-25 (378/378
      backend, frontend build succeeds; the `@hugeicons` PURE-annotation warnings during
      build are pre-existing/cosmetic, not new failures).
- [x] Report-mode (DS-STAR+) and domain-pack document upload still work end-to-end under
      real auth — one `task_type='report'` task completed under the real Google account
      (`3602b14e...`, 2026-08-23 20:55). Domain-pack **document upload** specifically still
      unconfirmed: `domain_pack_documents` table is empty (0 rows).
- [ ] Once all the above is clean: decide whether to commit/push this branch and open a PR
      (still nothing committed — all changes remain in the working tree on
      `feat/google-oauth-admin-panel`, confirmed via `git status` 2026-08-25).

**New since the 2026-08-23 entry, not previously documented here**: a "Continue as Guest"
(name-only, no real identity) login path exists (`POST /api/v1/auth/guest` in
`backend/main.py`), gated behind the `demo_mode` feature flag. 4 of the 5 users in the DB
are guest rows (`auth_provider='guest'`, no email/`google_sub`), created same-day as the
Google sign-in testing above. Not part of the original OAuth/admin-panel scope — picked up
in the same working-tree session — and not yet reflected anywhere else in this file.

**What was built:**
- **Backend** (`auth.py` rewritten, `main.py` extended): Google Identity Services credential
  verified server-side (`google-auth`), own signed session cookie (`pyjwt`, HS256, no
  `sessions` table — the cookie carries `user_id`, every request re-loads the `users` row
  fresh for ban/admin status). New `users` table (`db/init.sql` +
  `backend/migrations/2026-08-23_users_and_admin_config.sql` for the already-running DB).
  `POST /api/v1/auth/google`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
  `admin_list_users`/`admin_ban_user`/`admin_unban_user`/`admin_list_admins` now real
  DB-backed behavior (previously a single fake user, ban/unban 501s). CORS gained
  `allow_credentials=True` for the cross-origin cookie.
- **Prompt editor**: `agents/prompt_store.py` (`get_prompt(agent, default)`, DB row wins,
  fails closed to the hardcoded constant on any error) wired into the 8 agents with a
  single-string prompt (`analyzer`/`debugger`/`finalizer`/`query_clarity`/
  `question_generator`/`report_evaluator`/`router`/`verifier`). `planner`/`writer`
  deliberately excluded — each builds its prompt from more than one hardcoded piece
  (PLANNER_INIT/PLANNER_NEXT, a domain-pack-composed template), so a single free-text
  override doesn't safely cover them; flagged as a follow-up, not silently dropped. New
  `agent_prompts` table, `GET/PUT /api/v1/admin/prompts`, `POST .../reset`,
  `AdminPromptsPanel.jsx`.
- **Per-agent model override**: `llm_router.py`'s `get_model_override()` checked before the
  existing `_AGENT_OVERRIDES`/tier lookup. New `agent_model_overrides` table,
  `GET/PUT /api/v1/admin/models` (dropdown populated from the live Ollama tag list, not
  free text — avoids a typo'd model id 404ing every task), `AdminModelsPanel.jsx`.
- **Data visibility** (read-only this pass, no raw-data upload/delete yet):
  `GET /api/v1/admin/documents` (domain-pack knowledge base documents across every pack,
  not just one at a time), `GET /api/v1/admin/data-files` (the `data/` directory the
  sandbox/analyzer read directly), `AdminDataPanel.jsx`.
- **Frontend auth wiring**: Google Identity Services script tag (`index.html`,
  `admin.html`), `Login.jsx` (recreated, new provider), `useAuth.js` rewritten as a real
  hook, `App.jsx`/`AdminApp.jsx` regain real login gates.
- **Demo-polish fixes found during exploration, done alongside**: removed the dead
  "Dashboard — Coming soon" sidebar nav item and the permanently-disabled "Steer the
  analysis" input (both were the only two spots in the whole UI that visibly said
  "not done"); added `system: "Queued"` to `PipelineTimeline.jsx`'s agent-label map so
  the concurrency-queue log line renders properly if two tasks are demoed back to back;
  added a top-level React error boundary (`ErrorBoundary.jsx`) around both `App.jsx` and
  `AdminApp.jsx` — no blank-white-screen risk during a live demo.
- Not done (explicitly out of scope for this pass, not forgotten): rebranding `brand.js`
  away from its fraud/AML-flavored sample prompts (content decision, not mine to guess),
  dark mode, audit log / execution-log viewer / usage-cost dashboard from the original
  "additional features" wishlist.

The detailed scoping notes below (Part 1/Part 2/"Ordered steps") are the original
2026-08-22 plan this entry executed against — kept as design-rationale reference (the
"why" behind the choices above), not a separate to-do; the "Built" summary above is the
current state of record.

### Part 1 — Google OAuth

**What the user asked for**: sign-in via a real Google account, storing "just the
username," not passwords. Worth being explicit about something already true by
construction: **OAuth never gives the app the user's Google password at all** — that's
the entire point of the protocol, Google authenticates the user on Google's own page and
hands the app a signed identity token, nothing else. So "don't save the password" isn't
an extra precaution to design in, it's just how this works; what actually needs deciding
is what to store from that token (email seems to cover "just the username" — see open
questions below).

**Technical approach — do NOT re-introduce GoTrue/Supabase Auth.** That's the exact
complexity today's migration removed. Self-contained alternative, no new services:
- **Frontend**: Google Identity Services (`accounts.google.com/gsi/client`, no npm
  package needed — a single script tag). Renders Google's own "Sign in with Google"
  button, returns a signed JWT credential directly to the frontend — no OAuth redirect
  dance to build.
- **Backend**: verify that JWT server-side with Google's `google-auth` Python library
  (`google.oauth2.id_token.verify_oauth2_token`, checked against Google's public keys —
  no secret round-trip needed for verification itself, only for obtaining a Client ID).
  On a valid token, look up or create a row in a new `users` table (`db/init.sql`) keyed
  by the token's `sub` (Google's stable per-account id) with `email` and `name` from the
  token claims — nothing else. Issue this app's own session (signed cookie or a
  `sessions` table + opaque cookie token, still no GoTrue).
- `backend/auth.py`'s `get_current_user`/`get_current_admin` go back to real per-request
  checks (reversing today's stub) — reads the session, looks up the `users` row. Every
  `.eq("user_id", user.id)` call site in `main.py` still works unchanged since `user.id`
  still exists, just no longer always the same fixed uuid.
- `frontend/src/hooks/useAuth.js` goes back to a real hook (session check + Google
  sign-in button), `App.jsx`/`Sidebar.jsx`/`admin/AdminApp.jsx` regain their login gates —
  essentially reverting today's stub commits for these files, not writing them from
  scratch.

**Needed from the user before this can start** (genuinely blocking, not a "don't re-ask"
item):
- A Google Cloud OAuth Client ID (Google Cloud Console → APIs & Services → Credentials →
  "OAuth client ID", type "Web application", with `http://localhost:5174` as an
  authorized JavaScript origin). No client *secret* is needed for the Identity Services
  flow above — just the Client ID, which is not sensitive and can live in
  `VITE_GOOGLE_CLIENT_ID`.
- **Who's allowed to log in** — three options, pick one: (a) any Google account (open
  sign-up, matches "real Google account" literally but means anyone who finds the URL
  can create a task-history row), (b) an email allowlist (same shape as the old
  `ADMIN_EMAILS` pattern, just for login rather than admin-only), (c) restrict to a
  specific Google Workspace domain via the token's `hd` claim (only relevant if this is
  ever exposed beyond localhost). Given this is still a single-machine local tool today,
  (b) is the closest match to the spirit of "single trusted local machine" the rest of
  this migration was built around — but that's a guess, not confirmed with the user.
- **Admin identity**: with real accounts back, `get_current_admin` needs a real
  allowlist again too (bring back something like `ADMIN_EMAILS`, checked against the
  logged-in Google email) — confirm whose email(s) should be admin.

### Part 2 — Admin Control Panel

Existing admin surface (`frontend/src/admin/`) already covers: feature flags
(`FeatureFlagsPanel`), task list/stop/rerun/delete (`AdminTasksPanel`), domain packs
(`AdminDomainPacksPanel`), users (`AdminUsersPanel` — currently a stub post-auth-removal,
needs real content once Part 1 lands), system health (`AdminSystemPanel`). What's
missing, mapped to the user's ask:

- **Prompt editor, per agent** ("control the prompts of different agents"). Every agent's
  prompt is a hardcoded Python string constant today — `ANALYZER_PROMPT`
  (`agents/analyzer.py`), `FINALIZER_PROMPT` (`agents/finalizer.py`), and 7 more across
  `agents/{question_generator,query_clarity,debugger,report_evaluator,router_agent,
  verifier}.py`. To make these admin-editable without a redeploy: a new `agent_prompts`
  table (`agent_name` PK, `prompt_text`, `updated_at`) in `db/init.sql`; each agent
  reads its DB row if present, falling back to today's hardcoded constant as the
  default (so an empty table doesn't change behavior — matches the pattern
  `domain_pack_configs` already uses). Admin UI: one panel, agent picker, a textarea,
  Save/Reset-to-default. Worth a "view diff from default" affordance and *some* history
  (even just "last edited at/by") so a bad prompt edit is recoverable — flag this as a
  real risk: a bad prompt change degrades every task silently, unlike a bad feature-flag
  toggle which is at least visible immediately.
- **Per-agent model/tier config** ("the levels that we have set for each of the
  agents"). Today this is `llm_router.py`'s hardcoded `AGENT_TIERS` dict (high/medium/
  low per agent) plus `_AGENT_OVERRIDES` (coder/debugger/finalizer pinned to
  `OPENROUTER_MODEL_CODER` regardless of tier) plus the existing DB-backed
  `llm_speed_profile` toggle (`app_settings`, already has an endpoint:
  `/api/v1/llm_speed_profile`). Natural extension: a DB-backed per-agent override table
  (`agent_model_overrides`: `agent_name` PK, `model_id`) checked before the tier lookup
  in `LLMRouter.complete`, same shape as the code-generation override already there.
  Admin UI: a table, one row per agent, showing effective tier + model, editable per
  row. Since this is a local-Ollama deployment, worth surfacing which local Ollama tags
  exist (`GET http://host_ollama/api/tags`, already how `/health`'s LLM check works) as
  a dropdown rather than a free-text model id field — reduces "typo'd a model name and
  every task now 404s" risk.
- **Data management** ("data thats been uploaded"). Two distinct things share this name
  today, worth disambiguating with the user rather than guessing which they meant: (a)
  domain-pack documents — already has upload/list/delete
  (`upload_domain_pack_document`/`list_domain_pack_documents`/
  `delete_domain_pack_document` in `main.py`, RAG-ingested), just no admin-side view of
  them across all packs at once (today's `AdminDomainPacksPanel` manages pack configs,
  not their documents); (b) the raw `data/` directory the sandbox/analyzer read
  directly (CSVs, currently only ever populated by `scripts/fetch_datasets.sh` or manual
  drop-in, no upload UI, no delete UI, no listing UI at all). A real "data management"
  panel probably wants both: a cross-pack document browser for (a), and a basic file
  manager (list/upload/delete, sizes, maybe a row-count/column-preview via the existing
  analyzer machinery) for (b).
- **Additional features worth adding**, since the user invited more ("add more
  features") — not yet scoped in detail, listed here so they're not lost:
  - **Audit log** for admin actions (prompt edits, model overrides, feature flag
    flips, user bans) — who changed what, when. Especially important once prompt
    editing exists (see the "silently degrades every task" risk above) and once real
    multi-user auth exists (more than one person could plausibly hold admin).
  - **Execution/sandbox log viewer** — recent script executions with stdout/stderr,
    surfaced from the same data `agents/executor.py`/`agents/finalizer.py` already log,
    just not currently browsable outside a single task's own log timeline. Useful for
    debugging exactly the kind of live bug found and fixed earlier today (Finalizer
    printing non-JSON) without grepping `docker logs`.
  - **Usage/cost dashboard** beyond the current per-task stat strip — token usage over
    time, broken down by agent, using the same `debug_attempts`/token-count data
    `llm_router.py` already returns per call but doesn't currently persist anywhere
    aggregable.
  - **User list with real content** — `AdminUsersPanel` exists today but is a stub
    (single fixed local user, ban/unban return 501) as a direct consequence of today's
    auth removal; Part 1 landing makes this panel meaningful again (real accounts to
    list/ban), so treat it as revived rather than newly built.

**"Research to make it look like a control panel"**: read as a design-quality bar, not a
specific feature — study how real ops/admin dashboards are laid out (dense data tables,
a persistent left-nav between sections, inline edit affordances, status/health chips)
rather than the current flat single-page-per-section pattern. Load the `artifact-design`
or general dashboard-layout conventions when this is actually built, not just the
feature list above.

### Ordered steps for whoever picks this up

1. Get the two blocking decisions from the user (Google Client ID + who's allowed to log
   in / who's admin) — cannot proceed past a login *button* without them.
2. `users` table + session mechanism (`db/init.sql`, `backend/auth.py`) — Part 1's core.
3. Restore real `get_current_user`/`get_current_admin`, restore frontend login gates
   (`useAuth.js`, `App.jsx`, `Sidebar.jsx`, `AdminApp.jsx`) — reverting today's stub
   commits for these specific files.
4. Smoke test: real Google sign-in round-trip, a task submitted under a real account,
   `tasks.user_id` resolving to that account's row, not a fixed uuid.
5. `agent_prompts` + `agent_model_overrides` tables, backend read-with-fallback wiring
   in each `agents/*.py` file + `llm_router.py`.
6. New admin panels: prompt editor, model/tier config, data manager — in whatever order
   the user prioritizes (not decided yet).
7. Additional features list above — pick up opportunistically, none blocking the core
   ask.

## Archived scoping notes (superseded by the Completed entry above — kept for the two
## corrections' context, safe to delete once the "Remaining" items above are closed)

Goal: make the whole app run fully offline on one machine — no OpenRouter (already done,
see above) and no hosted Supabase. Follows on from the local-LLM work above; picked up in a
fresh session to save context, so everything found during scoping is written out below
rather than assumed re-derivable.

**Decisions already made (don't re-ask)**:
- Auth: **drop entirely** — single local user, no login screen, no JWT. Chosen over
  self-hosting Supabase's full stack (GoTrue+Studio+Realtime) or writing custom multi-user
  auth — this is a single-machine personal tool now.
  **⚠ Superseded 2026-08-22, later the same day** — see "Planned — Google OAuth login +
  Admin Control Panel" further down. The user asked for real Google sign-in back after
  using the app auth-free for a few hours. Everything below this note is still accurate
  history of *why* auth was dropped and *how* — useful context for the reversal — just no
  longer the target end state.
- Data: **fresh start, no migration** — stand up the new local schema empty. Today's hosted
  task history/domain packs are not carried over. Keep the hosted Supabase project
  untouched/available as a fallback until the local setup is verified working, don't
  delete/pause it as part of this work.

### What Supabase is actually providing (verified live, not assumed)

Checked directly against the live project — `specs/database-schema.sql` is **stale/aspirational
docs, not the real schema** (it lists tables like `users`/`analysis_sessions`/`agent_steps`
that don't exist; real tables found via `pg_tables`):

| Real live table | RLS enabled | Notes |
|---|---|---|
| `tasks` | yes (`select/insert/update_own_tasks`, keyed to `user_id`) | core task state |
| `domain_pack_chunks` | yes (`authenticated can read chunks`) | RAG chunks, `vector(768)` as of today's embeddings migration |
| `domain_pack_configs` | yes (`authenticated can read pack configs`) | |
| `domain_pack_documents` | yes (`authenticated can read documents`) | |
| `app_settings` | yes (`authenticated can read app settings`) | |
| `file_descriptions` | no | analyzer's per-file description cache |
| `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | no | LangGraph's own Postgres checkpointer tables — auto-created on first connection by `langgraph-checkpoint-postgres`, never need dumping |

Live Postgres: **17.6**. Extensions in use: `vector` (0.8.0), `pgcrypto`, `uuid-ossp`,
`pg_stat_statements`, `plpgsql`. `supabase_vault` is present but **confirmed unused** by any
app code (grepped) — don't bother replicating it.

Supabase pieces actually in play, and what replaces each:
- **Postgres** → `pgvector/pgvector:pg17` Docker image (exact version match)
- **PostgREST** (Supabase's auto-REST layer — every `supabase.table(...).select()...execute()`
  call in the backend goes through this, not raw SQL) → self-host the same open-source
  `postgrest/postgrest` image. This is the key fact that makes the migration tractable
  without rewriting every DB call: `supabase-py` is just a PostgREST HTTP client, it doesn't
  care whose PostgREST it's talking to.
- **GoTrue (Auth)** → dropped entirely, see below
- **Storage** → not used anywhere, confirmed, nothing to replace
- **Realtime** → not used, frontend polls via plain GET, no subscriptions

### The auth-removal mechanism (the non-obvious part)

PostgREST only validates JWTs if `PGRST_JWT_SECRET` is configured. **Leave it unset** and set
`PGRST_DB_ANON_ROLE` to a Postgres role with full grants on the app's tables — PostgREST then
treats *every* request as that role regardless of what's in (or missing from) the
`Authorization` header. `supabase-py` keeps sending its `Bearer <key>` header unchanged;
PostgREST just ignores it. Net effect: no JWT generation/secret/rotation, no GoTrue container,
and `auth.py`'s `get_current_user`/`get_current_admin` collapse to a stub returning one fixed
local user object (fixed UUID + email) — every existing `.eq("user_id", user.id)` call in the
codebase keeps working unchanged, just always resolving to that one id. RLS policies on the 5
tables above get dropped (they exist for hosted multi-tenant isolation; pointless on a single
trusted local machine with no public exposure).

### Frontend auth surface (both places, nothing else touches Supabase)

- `frontend/src/api.js` — axios request interceptor calls `supabase.auth.getSession()` to
  attach the bearer token. Remove the interceptor.
- `frontend/src/App.jsx` — gates the whole app behind `<Login/>` if no session. Remove the
  gate, always render the main app.
- `frontend/src/lib/supabaseClient.js` — the only file that imports `@supabase/supabase-js`
  on the frontend. Delete it; remove the npm dependency.
- `docker-compose.yml`'s frontend build args `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` —
  remove.

### docker-compose additions

```yaml
postgres:
  image: pgvector/pgvector:pg17
  environment: [POSTGRES_PASSWORD=...]
  volumes:
    - pgdata:/var/lib/postgresql/data
    - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
  healthcheck: pg_isready

postgrest:
  image: postgrest/postgrest
  depends_on: { postgres: { condition: service_healthy } }
  environment:
    PGRST_DB_URI: postgresql://postgres:...@postgres:5432/postgres
    PGRST_DB_SCHEMA: public
    PGRST_DB_ANON_ROLE: dsstar_app   # deliberately no PGRST_JWT_SECRET — see above
  ports: ["3001:3000"]
```

`db/init.sql` = a fresh `pg_dump --schema-only` of the **real live schema** (not the stale
spec file), sanitized: strip RLS policies, strip the (unused) `supabase_vault` extension,
keep `vector`/`pgcrypto`/`uuid-ossp`/`pg_stat_statements`. Don't include the `checkpoint*`
tables — `langgraph-checkpoint-postgres` creates those itself on first connect.

### Env var changes

`SUPABASE_URL` → `http://localhost:3001`; `SUPABASE_DB_URL` → local Postgres connection
string; `SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_KEY` → any placeholder string (never actually
checked once `PGRST_JWT_SECRET` is unset).

### Ordered steps for whoever picks this up

1. `pg_dump --schema-only` the live Supabase Postgres (`SUPABASE_DB_URL` is in
   `backend/.env`; use `psycopg` in a `uv run python -c "..."` one-liner if the `psql` CLI
   isn't installed in this environment — it wasn't, during scoping), sanitize per above into
   `db/init.sql`
2. Add `postgres`+`postgrest` services to `docker-compose.yml`, bring up, verify PostgREST
   actually serves the schema (`curl localhost:3001/tasks` should 200 with an empty array,
   not error)
3. Stub `backend/auth.py` for the single local user (both `get_current_user` and
   `get_current_admin`)
4. Strip the 3 frontend files listed above
5. Repoint all env vars in `backend/.env`, restart backend
6. Smoke test for real: submit a QA task, submit a report task, ingest a domain-pack document
   and confirm RAG retrieval — all against the local stack, not mocked
7. Only after step 6 passes clean: decide whether to pause/decommission the hosted Supabase
   project (don't do this preemptively — it's the safety net until local is proven)

### Related, discovered while scoping today (fold in if convenient, not required)

The stuck-task bug noted in the "Fully local LLM stack" entry above (a Supabase Postgres
connection's send queue stalling mid-write, leaving a completed task's status frozen at
`"running"`) is a class of flakiness specific to a network hop to a hosted DB — worth
confirming it doesn't recur once Postgres is `localhost`, as an implicit validation that this
migration was worth doing beyond just "offline for its own sake".

## Product differentiators (good → wow)

Distinct from the hardening/tech-debt backlog below — these are the features that would most
change how DS-STAR *feels* to use, not just how safe/correct it is. Roadmap order is a
judgment call (checkpoints first — see rationale), not a commitment.

- [x] General interrupt/resume mechanism — see Completed above (Stop/Pause/Resume). The
      `AsyncPostgresSaver` checkpointer is now actually wired up and working (was silently
      broken — see completed entry).
- [x] **Report-mode paper fidelity — citation round-partitioning + refine/finalize HITL
      checkpoint** (PR #15 follow-up, `b413015`). Structural fidelity audit (prior session)
      compared the actual DS-STAR+ paper spec, this repo's own never-implemented planning
      doc (`specs/agents/writer.md`), and what was actually built. Two gaps identified,
      both now closed:
      1. **Citations now partition by round.** `writer.py`'s `_citation_label()` gives the
         initial round numeric labels (`[1]..[N]`) and each refine round its own alphabetic
         labels (`[a]..[z]` for the first refine round, round-prefixed `[2a]..[2z]` for a
         second, since the paper doesn't specify a scheme beyond one refine round and
         unprefixed letters would collide across rounds). `agents/state.py` gained
         `sub_question_rounds` to track which round each sub-question was added in
         (`question_generator.py` stamps round 0, `graph.py`'s `gap_question_generator`
         stamps the current refine round). `report.sources` now carries a `round` field;
         `ReportView.jsx` shows a "Refine round N" badge on those source entries.
      2. **Human refine-vs-finalize checkpoint added, opt-in.** New `require_human_review`
         flag (off by default — an explicit product choice, not every report run should
         pay the friction) on `TaskSubmission`/`TaskState`. When set, a new
         `human_review_gate` node (`graph.py`) sits between `report_evaluator` and
         finalize/refine, reusing the existing Stop/Pause cooperative-interrupt/
         checkpoint-resume mechanism (`agents/cancellation.py`'s `AwaitingReview`
         exception + a `_review_decisions` store) rather than inventing a new pause
         primitive — skipped automatically at the round limit, where there's no real
         choice left. New `POST /api/v1/tasks/{id}/review` endpoint
         (`{"decision": "refine"|"finalize"}`), new `awaiting_review` task status, and
         `stop_task` extended to handle stopping a task parked at this checkpoint (no
         in-flight graph run to cooperatively interrupt there, so it stops directly).
         Frontend: opt-in checkbox in `EmptyState.jsx` (report mode only), an indigo
         review card in `ReportPanel.jsx` showing the evaluator's actual verdict/gaps
         (from `tasks.logs`, not placeholder text) with Finalize/Refine buttons.
      Everything else the original audit found (a Methodology section, standalone
      HTML+PDF export via Playwright) traces back to this repo's own abandoned planning
      doc, not the paper itself — optional polish, not fidelity gaps, not tracked here.
      25 new backend tests (routing, the gate node, the cancellation store, the endpoint's
      404/409/422/happy-path cases); full suite green in CI before merge.
- [ ] Live streaming (WebSocket/SSE) instead of 2s polling of the `tasks.logs` JSONB array —
      pipeline runs would feel real-time instead of laggy, especially in report mode.
- [ ] Follow-up / conversational refinement without a full pipeline re-run — e.g. "now break
      that down by region" as a cheap continuation using existing context.
- [ ] Real data connections beyond local CSVs dropped in `data/` — no MySQL/Postgres/
      warehouse connector, no catalog. Currently a hard wall between "demo" and "plugs into
      a team's actual stack."
- [x] Citations/traceability in report mode (DS-STAR+) — see Completed above.

## Audit remediation — remaining (roadmap order)

All 9 original P0 launch blockers are now closed except environment separation, which is an
explicit, accepted deferral (see below) rather than outstanding work.

### P1 — before real users
- [ ] Malformed LLM JSON silently defaulted in 3 places (`report_evaluator` defaults to
      "sufficient" on parse failure)
- [ ] No schema validation of LLM JSON before the frontend renders it
- [ ] Dashboard stale-response race condition on rapid task switching
- [ ] Global filename-only file-description cache can return the wrong dataset
- [ ] 11/16 backend agent files have zero test coverage (`finalizer.py`, `planner.py` now
      covered)
- [ ] Zero frontend tests, no test framework configured
- [ ] No React error boundary
- [ ] Results table has no pagination/virtualization
- [ ] Container from a timed-out script isn't guaranteed to be killed
- [ ] No request size limits / rate limiting on task submission
- [ ] LLM-generated scripts can emit invalid f-string format specs (observed: `{x:, .2f}` — a
      stray comma before the format spec, from the Finalizer's formatting step) and crash with
      `ValueError` at execution time, failing the task outright

### P2 / P3 — hardening & polish
- [ ] Sandbox missing CPU/pids limits, read-only rootfs, capability drop
- [ ] Untrusted file content unescaped in LLM prompts (injection surface)
- [ ] Raw stderr/tracebacks persisted and served through the API
- [ ] `npm run lint` fails (26 errors) — mostly vendored shadcn boilerplate
- [ ] README roadmap misrepresents current state
- [ ] Unbounded read-modify-write on the logs array (race-prone)
- [ ] No git tags / CHANGELOG / rollback mechanism
- [ ] Loosely pinned backend deps, no upper bound
- [ ] Sandbox base image not pinned to a digest
- [ ] `task_id` not validated as UUID before query
- [ ] Prompt-formatting duplication across 6 agent files
- [ ] Duplicated JSON-parsing / chart-style / follow-up-bar code (`ReportView` vs
      `ReportSections`)
- [ ] Frontend bundle inflated 1.6MB by one icon package (`@hugeicons`, only 2 icons used)
- [ ] Silent console-only failures on task-list/poll fetch errors
- [ ] Sortable table headers not keyboard/screen-reader accessible
- [ ] Completed task with an empty result gets stuck in the loading UI forever
- [ ] Commented-out dead code + `router`/`router_agent` naming collision (backend)
- [ ] 66 arbitrary Tailwind pixel values fragment the type scale

## Deferred (explicit user decision)
- [ ] Rotate exposed Supabase/Gemini credentials — deferred, not forgotten
- [ ] No environment separation (single Supabase project for dev/test/prod) — Supabase's free
      tier caps active projects at 2 (paused ones don't count), which is enough for a real
      dev/prod split, but the user chose to stay on a single project for now. Revisit if this
      goes anywhere near real user data — CI itself is unaffected either way, it already runs
      against mocked/dummy credentials, never a real project.

---
Full findings detail: published audit artifact *"FIP / DS-STAR — Production Readiness & Code
Health Audit"*.
