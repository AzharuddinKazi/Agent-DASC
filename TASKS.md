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

## Audit remediation — remaining (roadmap order)

### P0 — before this leaves localhost
- [ ] No deployable artifact (backend/frontend Dockerfiles, compose)
- [ ] No environment separation (single Supabase project for dev/test/prod)
- [ ] No structured logging / error tracking
- [ ] No concurrency limit on pipeline execution

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
- [ ] CORS hardcoded to dev origin
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

---
Full findings detail: published audit artifact *"FIP / DS-STAR — Production Readiness & Code
Health Audit"*.
