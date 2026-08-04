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

Re-audited 2026-07-30 against actual code (not just tracker wording) — 2 resolved, 3 partially
resolved, 6 still pending, 0 increased. Worked through one-by-one starting 2026-08-03; all 9
are now resolved (see each item below for what changed and why).

- [x] ~~Malformed LLM JSON silently defaulted in 3 places (`report_evaluator` defaults to
      "sufficient" on parse failure)~~ — **resolved**: `report_evaluator.py` now treats a
      parse failure as `"insufficient"` with no gaps (bounded by `max_report_rounds`, so it
      can't loop forever) instead of silently claiming the report passed QA, logs a
      `logger.warning` plus an `"error"`-level `log_event` entry (`parse_failed: true`) so the
      failure is visible instead of invisible, and switched to the shared
      `agents/code_fences.py` stripper instead of its own inline regex. 2 tests updated to
      match, suite green (261 passed).
- [x] ~~No schema validation of LLM JSON before the frontend renders it~~ — **resolved**:
      new `agents/schemas.py` defines Pydantic models (`FinalizerOutput`, `WriterReport`,
      with their nested `chart`/`sections`/`risk_matrix`/`data_coverage` shapes) matching
      what the Finalizer/Writer prompts ask the LLM to produce and what the frontend
      (`ReportSections.jsx`, `ReportView.jsx`) assumes. `finalizer.py` and `writer.py` now
      validate their parsed JSON against these after `json.loads` succeeds and log the
      concrete field errors (e.g. `"summary: Field required"`) via `logger.warning` when the
      shape doesn't match — visibility only, doesn't block or alter storage, matching the
      existing "log and ship degraded" pattern the codebase already uses elsewhere (see
      `report_evaluator` above, `writer`'s own non-JSON fallback). 7 new tests (schema
      module + one integration test per agent confirming a mismatch logs but doesn't break
      the pipeline); suite green (268 passed).
- [x] ~~Dashboard stale-response race condition on rapid task switching~~ — **resolved**:
      `Dashboard.jsx`'s polling effect now uses the same `cancelled`-flag guard as
      `useHealth.js` — set on effect cleanup (which fires on every `activeTaskId`/
      `pollGeneration` change, i.e. switching tasks or restarting polling), checked before
      `setTask(r.data)` and before logging a fetch error. A slow response for a task the
      user has since switched away from is now dropped instead of overwriting the current
      selection. No frontend test framework exists yet to add a regression test (separate
      pending item below) — verified via `npm run build` (succeeds) and `npx eslint` on the
      changed file (no new errors; the one pre-existing `react-hooks/set-state-in-effect`
      warning on line 36 predates this change).
- [x] ~~Global filename-only file-description cache can return the wrong dataset~~ —
      **resolved**: `analyzer.py`'s cache lookup now also compares a `content_hash` —
      `_content_fingerprint()` hashes file size + the first/last 64KB rather than the full
      file, since a true full-file SHA256 would mean re-reading every byte of every dataset
      (including the 470MB file this repo ships with, per CLAUDE.md) on every single
      analyzer run just to validate the cache. A same-name-same-size-different-content
      collision is now caught; old cache rows written before this migration (no
      `content_hash`) safely miss the cache once rather than being trusted. New nullable
      `content_hash` column added via `migrations/2026-08-03_file_descriptions_content_hash.sql`,
      applied to the live Supabase instance. 5 new tests (fingerprint stability/divergence,
      the actual collision scenario, backward-compat with hash-less rows); suite green
      (272 passed).
- [x] ~~11/16 backend agent files have zero test coverage~~ — **resolved**: 16 of 17
      non-`__init__` files in `backend/agents/` now have corresponding tests (spot-checked
      `test_coder.py`/`test_verifier.py` — real logic, not stubs). Only `logger.py` remains
      untested. Original count was stale even before this pass.
- [x] ~~Zero frontend tests, no test framework configured~~ — **resolved**: added
      `vitest` + `@testing-library/react`/`jest-dom`/`user-event` + `jsdom`, wired into
      `vite.config.js`'s `test` block (`src/test/setup.js`), `npm run test`/`test:watch`
      scripts, and a `Test` step in `.github/workflows/ci.yml` (runs before `Build`, not
      `continue-on-error` — unlike lint, this should actually gate). 6 tests across 2 files:
      `useHealth.test.js` (polling, error degradation, interval re-fire, stale-response-
      after-unmount) and `Dashboard.test.jsx` (regression coverage for the stale-response
      race just fixed above — verified it actually fails against the pre-fix `Dashboard.jsx`
      via `git stash`, not just that it passes now). `npm run test` and `npm run build` both
      green.
- [x] ~~No React error boundary~~ — **resolved**: new `components/app/ErrorBoundary.jsx`
      (must be a class component — React has no hook equivalent for
      `getDerivedStateFromError`/`componentDidCatch`), wrapping the view-switch in
      `App.jsx` and keyed by `view:taskId` so navigating away always remounts a fresh
      boundary rather than carrying a caught error into whatever's shown next. Its
      "Try again" button calls `onReset` (wired to `handleNew`, i.e. back to the empty
      state) rather than just clearing the error and re-rendering the exact same crash.
      3 new tests confirm it passes children through normally, catches a thrown render
      error instead of crashing the page, and calls `onReset` on retry. `npm run test`,
      `npm run lint` (no new errors), and `npm run build` all green.
- [x] ~~Results table has no pagination/virtualization~~ — **resolved**: `ReportSections.jsx`
      now paginates at 50 rows/page (`TABLE_PAGE_SIZE`) instead of mapping the full
      `sortedRows` into the DOM at once — Prev/Next controls, "Showing X–Y of N", and a
      page reset (adjusted synchronously during render, React's documented pattern for
      this — not an effect, which would cost an extra render and trips the
      `react-hooks/set-state-in-effect` lint rule) whenever the underlying rows or the
      active sort changes, so a re-sort or a new task never leaves `page` pointing past
      the new last page. CSV export is unaffected — it still writes the full `rows`, not
      just the visible page. Went with plain pagination over a virtualization library
      (react-window etc.) — this repo's row counts are the thousands, not
      millions-of-rows range virtualization exists for, and pagination is the simpler fix
      for the actual problem (DOM bloat from unbounded row counts). 5 new tests
      (no controls below the threshold, page navigation, boundary button disabling,
      reset-on-sort); suite green (14 passed), lint has 0 new errors (8 pre-existing
      unrelated warnings), build succeeds.

      **Follow-up regression found and fixed 2026-08-03** during a live end-to-end run
      (real query, real pipeline, real browser): the page-reset logic above compared
      `rows`/`columns`/etc. by reference, but their `parsed?.rows || []` fallback
      synthesizes a brand-new empty array every render whenever a result has no table
      data at all (a scalar-answer query, e.g. "what is the total number of X"). Dashboard's
      2s poll re-renders `ReportSections` periodically regardless of whether anything
      meaningful changed, and each of those re-renders' fresh empty array mismatched the
      previous one, re-triggering the reset, which triggered another mismatched re-render,
      etc. — React threw "Too many re-renders", genuinely caught live by the new
      `ErrorBoundary` (first real proof it works, not just its own unit tests) instead of
      white-screening. Fixed with a module-level stable `EMPTY_ARRAY` reused across all
      four `|| []` fallbacks in `ReportSections.jsx` instead of fresh literals. New
      regression test reproduces it correctly (mount + `rerender()` with unchanged props,
      since the bug requires a *second* render — a bare `render()` doesn't trigger it, the
      first render's `useState` initializer trivially matches itself) — verified it fails
      against the pre-fix code and passes after.
- [x] ~~Container from a timed-out script isn't guaranteed to be killed~~ — **resolved**:
      `executor.py`'s poll loop now explicitly `docker kill`s the per-run named container on
      every exit path (cancellation, pause, timeout) before raising/returning.
- [x] ~~No request size limits / rate limiting on task submission~~ — **resolved**:
      `TaskSubmission.query`/`formatting_guidelines` and `TaskClarification.query` are now
      Pydantic `Field(max_length=...)`-bounded (20K/5K/20K chars) instead of unbounded
      `str`. Added `slowapi` (in-memory, same reasoning as the `MAX_CONCURRENT_PIPELINES`
      semaphore — no new infra needed for a single-process deployment) rate-limiting
      `submit_task` (`SUBMIT_TASK_RATE_LIMIT`, default 20/minute) and `clarify_task`
      (`CLARIFY_TASK_RATE_LIMIT`, default 30/minute) — both cost a real LLM call,
      `submit_task` also a real Docker sandbox run, distinct from the semaphore's job of
      capping concurrent *execution*. Keyed by bearer token (`main._rate_limit_key`), not
      raw IP — IP-only keying would over-throttle callers behind a shared NAT/office IP
      while doing nothing to stop one user hitting the API from many IPs. A flood now gets
      a 429 instead of silently queuing forever. 3 new tests (oversized query → 422 for
      both endpoints, and an end-to-end rate-limit test that submits `limit + 1` requests
      under a dedicated bearer token — isolated from every other test's shared bucket —
      and asserts the last one 429s); suite green (275 passed). New env vars documented in
      `.env.example`.
- [x] ~~LLM-generated scripts can emit invalid f-string format specs (observed: `{x:, .2f}` —
      a stray comma before the format spec, from the Finalizer's formatting step) and crash
      with `ValueError` at execution time, failing the task outright~~ — **resolved**: new
      `agents/script_repair.py` repairs this exact defect (stray whitespace between the
      thousands-separator comma and the rest of an f-string format spec) unconditionally
      before every generated script runs — wired into `executor.execute_script`, the single
      choke point both the main coder→executor loop and the Finalizer's own script execution
      already go through, so the fix applies everywhere, not just the Finalizer's local retry.
      The regex is narrowly scoped to the literal `:,` + whitespace + spec + `}` signature,
      which has no legitimate Python meaning, to avoid false-positive rewrites. Also added
      preventive prompt guidance (the existing "never nest an f-string" rule already in
      `coder.py`/`finalizer.py`/`debugger.py` got a sibling rule for this pattern) so the
      model is less likely to produce it in the first place. 6 new tests (5 unit tests on the
      repair function's positive/negative cases, 1 integration test proving
      `execute_script` writes the repaired script, not the raw one, to the sandbox); suite
      green (281 passed).

### P2 / P3 — hardening & polish

**Resume-here note (2026-08-04):** working through this list one item at a time, in the
priority order below (correctness/security first, cleanup/cosmetic last). 12 of 18 done so
far. Remaining, in the agreed order:
1. Git tags/CHANGELOG/rollback mechanism — flagged for user input on approach, not just
   picked unilaterally, since it's a process/workflow decision more than a code fix
2. Prompt-formatting duplication across agent files
3. Duplicated JSON-parsing/chart-style/follow-up-bar code (`ReportView` vs `ReportSections`)
4. Frontend bundle inflated 1.6MB by `@hugeicons`
5. Silent console-only failures on task-list/poll fetch errors
6. Sortable table headers not keyboard/screen-reader accessible
7. Commented-out dead code + `router`/`router_agent` naming collision (backend)
8. 66 arbitrary Tailwind pixel values fragment the type scale

Working pattern per item (established over items 1–8, keep using it): implement → add/
update tests → run full suite → verify live against the running app when the change has
real runtime behavior (submit a real query through the browser, check backend logs) →
update this file → report back before moving to the next item. Two migrations were applied
to the live Supabase DB this session (`content_hash` column, `append_task_log` function) —
each required an explicit separate approval, don't assume blanket permission for further
DB writes.

- [x] ~~Sandbox missing CPU/pids limits, read-only rootfs, capability drop~~ —
      **resolved**: new `agents/sandbox_security.py` (`docker_security_args()`) adds
      `--cpus` (env-configurable `SANDBOX_CPUS`, default 2), `--pids-limit` (env
      `SANDBOX_PIDS_LIMIT`, default 128, against fork bombs), `--read-only` root
      filesystem with a `--tmpfs /tmp:size=256m` for well-behaved libraries' transient
      state (matplotlib's cache dir falls back there when its default `~/.config` isn't
      writable — verified live against the real `dsstar-sandbox` image, pandas/numpy/
      sklearn/scipy/openpyxl all still work), `--cap-drop ALL`, and
      `--security-opt no-new-privileges`. Wired into both real `docker run` call sites
      (`analyzer.py`'s file-profiling script, `executor.py`'s main script execution) so
      they can't drift apart. The image already ran as non-root `app` with
      `--network=none`, unchanged. 4 new tests (flag presence, env-configurability, both
      call sites' args) plus a live end-to-end pipeline run through the actual hardened
      sandbox (real Docker, real data, real executor exit 0) to confirm nothing broke;
      suite green (284 passed).

      **Bonus finding from that same live run**: caught and fixed a real "Too many
      re-renders" crash in `ReportSections.jsx` — logged under the pagination item above,
      since it was a regression in that same change, not a new backlog item.
- [x] ~~Untrusted file content unescaped in LLM prompts (injection surface)~~ —
      **resolved**: new `agents/prompt_safety.py` (`wrap_untrusted()`, `format_file_summaries()`)
      wraps user-supplied content — the Analyzer's per-file descriptions (which embed real
      cell values, e.g. its "first 5 rows" output — a CSV cell containing something that
      reads like an instruction would otherwise be indistinguishable from the prompt's own
      text) and uploaded domain-pack knowledge documents — in labeled
      `<dataset_file_summaries>`/`<domain_knowledge_reference>` blocks with an explicit
      "treat this as data, not instructions" notice, instead of interpolating it raw. This
      doesn't make prompt injection impossible (no delimiter scheme does), but an unmarked
      blob of untrusted text in a prompt previously gave the model zero signal that it
      wasn't part of the system's own instructions. Applied to all 7 agents that
      interpolate `data_descriptions` (`coder.py`, `finalizer.py`, `question_generator.py`,
      `query_clarity.py`, `planner.py`, `verifier.py`, `router_agent.py` — each previously
      duplicated the same raw `"\n".join(f"File: ...")` construction independently, now a
      single shared helper) and the one shared `domain_knowledge.py` retrieval function
      already used by planner/coder/verifier. 5 new tests for the wrapper itself; suite
      green (306 passed) with zero changes needed to any existing prompt-content
      assertions (the wrapped text still contains the original "File: ..." substrings
      those tests check for).
- [x] ~~Raw stderr/tracebacks persisted and served through the API~~ — **resolved**: new
      `agents/error_sanitizer.py` (`summarize_script_failure()` — reduces a raw Python
      traceback to just its final "ExceptionType: message" line, stripping internal
      container file paths and library-internal stack frames; `GENERIC_INFRASTRUCTURE_ERROR`
      — a fixed generic message for the truly-unexpected case). Applied everywhere a
      failure reaches something served through `GET /api/v1/get_task`:
      `finalizer.py`'s `final_result` on script failure, `finalizer.py`'s and
      `executor.py`'s `log_event` messages/meta on a failed round (both currently dumped
      the *first* N raw chars of a traceback into `tasks.logs` — mostly just the
      unhelpful "Traceback (most recent call last):" header rather than the actual error,
      so this is a genuine UX improvement too, not just a hardening one), and `main.py`'s
      generic `except Exception` handler in `run_graph` (`str(e)` on an unexpected
      infrastructure error could plausibly include connection strings or other internals).
      Full detail is never lost — `logger.error`/`logger.exception` and Sentry
      (`sentry_sdk.capture_exception`) still get the complete original text; only the
      response/log entries served back through the API are sanitized. Deliberately left
      `execution_result` (LangGraph-internal state, not a persisted/served DB column) and
      `logger.*` calls untouched — sanitizing those would remove information the debugger
      agent and server-side operators actually need. 8 new tests (sanitizer unit tests,
      finalizer/executor/run_graph integration tests proving file paths and a fake
      credential string don't survive into what's served); suite green (301 passed).
- [x] ~~`npm run lint` fails (26 errors) — mostly vendored shadcn boilerplate~~ —
      **resolved**: 20 of the remaining errors (count had already dropped from 26 by
      this session) were genuine vendored-shadcn boilerplate — an unused `import * as
      React` in 12 `components/ui/*.jsx` files (dead since the new JSX transform), an
      unused `useRef` in `ReportView.jsx`, `__dirname` undefined in `vite.config.js`
      (ESM — switched to `import.meta.dirname`), and a `useMemo` dependency-stability
      warning in `ResearchProgress.jsx` (same `EMPTY_ARRAY`-reuse fix as the earlier
      `ReportSections.jsx` pagination regression). The remaining 4 were
      `react-hooks/set-state-in-effect`, a stricter rule new in
      `eslint-plugin-react-hooks` v7's `recommended` config: one in `Dashboard.jsx`
      was a real instance of the antipattern the rule targets (resetting `task`/`isX`
      state synchronously at the top of the polling effect on every `activeTaskId`/
      `pollGeneration` change) — fixed by moving the reset to a render-time
      derived-state check keyed on `` `${activeTaskId}:${pollGeneration}` ``, the same
      "adjusting state when a prop changes" pattern `ReportSections.jsx` already uses
      for its page-reset, rather than restructuring the actual network-polling effect.
      The other 3 (`DomainPacks.jsx`) were standard fetch/poll-on-mount code — an
      async function that sets state after an `await`, not synchronously — which the
      rule can't distinguish from the real antipattern; addressed with scoped
      `eslint-disable-next-line` comments rather than forcing a data-fetching
      component into an unnatural shape to satisfy a rule limitation.
      `Dashboard.test.jsx`'s existing task-switch coverage (unchanged) still passes
      against the refactored reset logic — real regression protection, not just "it
      compiles." CI's frontend lint step, previously `continue-on-error: true`, now
      gates like `Test`/`Build`. `npm run lint` exits clean (0 errors, 0 warnings);
      `npm run test` (19 passed) and `npm run build` unaffected.
- [x] ~~README roadmap misrepresents current state~~ — **resolved**: both READMEs described
      an app that no longer exists in one major way and several minor ones. Biggest:
      both said "A Gemini API key" as the LLM prerequisite and `backend/README.md`'s
      "LLM routing" section described a Gemini `heavy`/`light` tier split — the backend
      has called OpenRouter exclusively for a while (`llm_router.py`,
      `OPENROUTER_API_KEY`, no `GEMINI_API_KEY` anywhere), with `high`/`medium`/`low`
      tiers and a live DB-backed `"free"`/`"fast_paid"` speed-profile toggle
      (`GET`/`POST /api/v1/llm_speed_profile`) neither README mentioned at all. Root
      README's feature description and pipeline diagram were also missing four shipped,
      TASKS.md-confirmed features: the `human_review_gate` HITL checkpoint, Stop/Pause/
      Resume task controls, DS-STAR+ citations, and the Domain Packs marketplace/RAG
      knowledge base — added to the intro paragraph and the report-pipeline prose.
      `backend/README.md`'s API table had 10 of 19 actual routes; rebuilt from
      `main.py`'s route decorators. Its agent-graph table was missing the
      `human_review_gate` node and `cancellation.py`/`query_clarity.py` (real files,
      no dedicated node) entirely; added, plus a note listing the cross-cutting
      `agents/` files (schemas, sanitizers, etc.) the table's "one file per node"
      framing undersold. Root README's stale "frontend has no automated test suite"
      claim (vitest was added weeks ago, per this file's own Completed section) fixed,
      plus a copy-paste bug in the new testing snippet (`cd frontend` after `cd
      backend` from repo root would fail — needed `cd ../frontend`). Also flagged
      `specs/agents/writer.md` and similar planning docs as historical/superseded
      rather than presenting `specs/` as uniformly current, per this file's own note
      that the writer spec's checkpoint design predates and differs from what was
      actually built. No code changes — docs only; not re-run through the test suite
      for that reason, but every route/env-var/model-tier claim was checked against
      the actual source (`main.py`, `graph.py`, `llm_router.py`, `.env.example`) before
      writing it down, not carried over from memory.
- [x] ~~Unbounded read-modify-write on the logs array (race-prone)~~ — **resolved**:
      `agents/logger.py`'s `log_event()` used to SELECT `logs`, append in Python, then
      UPDATE the whole array — a real race, not theoretical: a user's Stop/Pause request
      runs on the main event loop while the graph's currently-running node logs from
      `run_graph`'s background thread (`run_in_executor`), genuinely concurrently for the
      same `task_id`, and whichever write lost the race silently dropped its entry. New
      `append_task_log(p_task_id, p_entry)` Postgres function
      (`migrations/2026-08-03_atomic_log_append.sql`) makes the append atomic — a single
      `UPDATE ... logs = logs || entry` — with no read-modify-write window in application
      code at all. `log_event()` calls it via `supabase.rpc(...)` first and falls back to
      the old read-modify-write behavior only if the RPC itself fails (e.g. an environment
      that hasn't applied the migration yet), so logging degrades instead of breaking.
      Applied to the live Supabase instance — caught a real bug doing so: `tasks.task_id`
      is `uuid`, not `text`, and the first version of the function's `WHERE task_id =
      p_task_id` comparison failed with `operator does not exist: uuid = text` (missed by
      mocked tests, since none of them talk to a real Postgres) — fixed with an explicit
      `p_task_id::uuid` cast. 4 new tests for `logger.py` (previously the one untested
      agent file) covering the RPC path, the fallback path, and that logging never raises
      even if everything fails. Verified live end-to-end: submitted a real task through
      the running app and confirmed `POST .../rpc/append_task_log` returns `204` with no
      fallback warnings in the logs. Suite green (293 passed).
- [ ] No git tags / CHANGELOG / rollback mechanism
- [x] ~~Loosely pinned backend deps, no upper bound~~ — **resolved**: every dependency in
      `backend/pyproject.toml` (main + dev groups) now has an upper bound, not just a
      floor — capped at the next major version for already-1.0+ packages, and at the next
      *minor* for pre-1.0 packages (`fastapi`, `uvicorn`, `slowapi`, `python-multipart`)
      since semver treats a 0.x minor bump as a potential breaking change. Floors
      unchanged. Verified `uv sync` still resolves cleanly against the existing lockfile
      (no changes needed — everything already resolved falls within the new bounds) and
      the full suite stays green (301 passed).
- [x] ~~Sandbox base image not pinned to a digest~~ — **resolved**: `sandbox/Dockerfile`
      now pins `FROM python:3.12-slim` to the digest it currently resolves to
      (`@sha256:57cd7c3a...`) instead of a floating tag, which a registry or upstream
      rebuild can silently repoint without any signal here. Rebuilt `dsstar-sandbox:latest`
      against the pinned digest — same image ID as before (all layers cached, confirming
      nothing else changed) — and verified pandas/numpy/sklearn still import correctly.
      Bumping the pin is a deliberate manual step (re-pull the tag, take its new digest)
      by design, not automated — this is a rare, intentional action, not something worth
      a script for.
- [x] ~~`task_id` not validated as UUID before query~~ — **resolved**: `main.py`'s five
      `{task_id}` path routes (`get_task`, `stop_task`, `pause_task`, `resume_task`,
      `submit_review_decision`) now type the path parameter as `uuid.UUID` instead of
      `str` — FastAPI rejects a malformed path segment with 422 before the handler body
      (and therefore any DB query) ever runs, converted to `str(task_id)` on the first
      line of each handler so every existing downstream `.eq("task_id", ...)` call and
      response body is unaffected. Existing tests updated from placeholder strings
      (`"task-123"`, `"nonexistent"`) to actual UUID-format literals so their 404/409
      scenarios still reach the business logic; 5 new tests confirm a malformed id now
      gets a 422 and never touches `supabase` at all. Suite green (289 passed).
- [ ] Prompt-formatting duplication across 6 agent files
- [ ] Duplicated JSON-parsing / chart-style / follow-up-bar code (`ReportView` vs
      `ReportSections`)
- [ ] Frontend bundle inflated 1.6MB by one icon package (`@hugeicons`, only 2 icons used)
- [ ] Silent console-only failures on task-list/poll fetch errors
- [ ] Sortable table headers not keyboard/screen-reader accessible
- [x] ~~Completed task with an empty result gets stuck in the loading UI forever~~ —
      **resolved**: `ReportPanel.jsx` only had explicit branches for
      `completed && final_result`, `stopped`, and `failed` — a `status === "completed"`
      task with a falsy `final_result` (e.g. the generated script exited 0 but printed
      nothing) matched none of them and fell through to the loading/pipeline UI, which
      then had nothing left polling to ever move it forward (Dashboard's polling effect
      already stops once status leaves `"running"`), so it looked permanently stuck. Added
      an explicit terminal-state branch for this case with a clear message instead of a
      silent fall-through. 4 new tests (normal completed-with-result path still works,
      the new message shows for `null` and for `""` final_result, a genuinely running
      task still shows the loading UI); verified the new tests fail against the pre-fix
      code via `git stash` and pass after. Suite green (19 passed), build/lint clean.
- [ ] Commented-out dead code + `router`/`router_agent` naming collision (backend)
- [ ] 66 arbitrary Tailwind pixel values fragment the type scale
- [x] ~~Finalizer/Writer output containing a `NaN` value fails `JSON.parse` on the
      frontend~~ — **resolved**: new `agents/json_sanitize.py`
      (`sanitize_json_floats()`) recursively replaces `NaN`/`Infinity`/`-Infinity`
      floats with `None` before re-serialization — Python's `json` module accepts
      those tokens on both dump and load (unlike the JSON spec), so a generated
      script's output round-trips through `json.loads()` unchanged and would
      otherwise re-emit the same non-spec-compliant tokens the frontend's
      `JSON.parse` then rejects. Applied in `finalizer.py` (dict output: sanitized
      unconditionally, same place provenance is injected; non-dict/scalar or list
      output: sanitized only if a `has_non_finite_token()` pre-check finds one, so a
      plain-text or already-clean scalar result isn't needlessly re-dumped and
      reformatted) and `writer.py` (report is always a dict). 9 new tests
      (`test_json_sanitize.py` unit tests plus one integration test per agent, plus
      a byte-for-byte "untouched when clean" regression test for the finalizer's
      non-dict path); suite green (315 passed).

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
