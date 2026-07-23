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

## Audit remediation — remaining (roadmap order)

### P0 — before this leaves localhost
- [ ] No CI/CD pipeline
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
- [ ] `test_planner.py` makes live, unmocked DB calls — 4 tests fail on a UUID validation
      error (root cause of the credential-leak-in-logs issue noted in the original audit)
- [ ] 12/16 backend agent files have zero test coverage (`finalizer.py` now has coverage)
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
