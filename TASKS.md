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
