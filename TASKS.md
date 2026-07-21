# DS-STAR Task Tracker

## Checkpoint: 2026-07-18 — Specs locked, rebuilding from scratch (TDD)

The `[x]` items below reflect a first-pass implementation that was written before the specs
were reviewed and locked in. That review (2026-07-18) surfaced real deviations between the
old code and the specs (e.g. Analyzer skipping Debugger repair, dict/dataclass mismatches,
a network_mode contradiction in the sandbox executor) — see `specs/agents/*.md` and
`specs/features/*.md` for the `[LOCKED]`-tagged sections, which are now the source of truth.

**Decision: discard the old implementation and rebuild from scratch.** Order of work:
1. Write tests first, against the locked specs — one agent/feature at a time.
2. Only then implement the agent/feature to make those tests pass.
3. Repeat per component, in pipeline order (see below).

The checklist below is being reset to reflect this. Old `[x]` marks are kept struck through
for history but do not mean "done" anymore — nothing is done until it's rebuilt against the
locked specs.

---

## Phase 0 — Scaffolding
- [x] Repo structure (`pyproject.toml`, `.env.example`, `.pre-commit-config.yaml`, `config.yaml`)
- [x] Config + settings (`backend/config.py`, `backend/database.py`)
- [x] Prompts loader + `specs/prompts.yaml` (verbatim paper prompts)
- [x] **2026-07-20**: `specs/database-schema.sql` reviewed and locked against all Phase-1
      checkpoint decisions:
  - Added `checkpoint_type = 'refine_round_review'`
  - Split `checkpoints.status` (pending/resolved/abandoned) from a new `checkpoints.action`
    column (the specific choice: approve/reject/hint/refine_further/finalize/
    start_fresh_session — varies per checkpoint_type, see the file's inline comment)
  - Added `subquestion_generator`, `writer` to `agent_steps.agent_name` CHECK (were missing
    entirely — DS-STAR+ runs would never have been audit-logged)
  - Added `analysis_sessions.forked_from_session_id` (self-referencing FK) for
    `start_fresh_session` provenance
- [x] **2026-07-20**: `backend/migrations/001_initial.sql` and `backend/models.py` deleted —
      both had already drifted from `specs/database-schema.sql` (extra ad hoc columns like
      `mode`/`final_result`, no `agent_name` CHECK, old 4-value checkpoint enum) independent
      of the locked-decision gaps above. Both are part of the discarded first-pass backend
      per the 2026-07-18 checkpoint — regenerate fresh from the now-locked spec when Phase 0
      implementation actually starts, don't resurrect the old files.

## Phase 1 — Agents (tests first, then implementation, in pipeline order)

For each agent: write unit tests against the locked spec → implement → tests pass → move on.

- [x] Analyzer — tests, then implementation (spec: `specs/agents/analyzer.md`). **2026-07-20**:
      9/9 unit tests passing (`tests/unit/agents/test_analyzer.py`,
      `backend/agents/core/analyzer.py`). Debugger dependency is injected via `debug_fn`
      (defaults to a lazy import of `backend.agents.core.debugger.run_debugger_analyzer_repair`,
      only resolved on actual failure — Debugger itself isn't built yet, tests mock it).
- [ ] Planner (init + next) — tests, then implementation (spec: `specs/agents/planner.md`)
- [ ] Coder (init + next) — tests, then implementation (spec: `specs/agents/coder.md`)
- [ ] Debugger (summarize + analyzer repair + coder repair) — tests, then implementation (spec: `specs/agents/debugger.md`)
- [ ] Verifier — tests, then implementation (spec: `specs/agents/verifier.md`)
- [ ] Router — tests, then implementation (spec: `specs/agents/router.md`)
- [ ] Finalyzer + mode auto-detection/override — tests, then implementation (spec: `specs/agents/finalyzer.md`)
- [ ] SubquestionGenerator (init + refine, 8/round cap) — tests, then implementation (spec: `specs/agents/subquestion-generator.md`)
- [ ] Writer (init + refine) — tests, then implementation (spec: `specs/agents/writer.md`)

## Phase 2 — Features

- [ ] Sandbox executor — Docker (fixed network model) + Cloud Run backends (spec: `specs/features/sandbox-execution.md`)
- [ ] Catalog scanner — MySQL (with enforced read-only check) + file sources (spec: `specs/features/catalog.md`)
- [ ] Checkpoints/HITL handler — 5 checkpoint types incl. new `refine_round_review`, 2-round force-exit cap (spec: `specs/features/checkpoints-hitl.md`)
- [ ] GraphRAG ingestion (incremental `update` on upload, full rebuild on delete) + retrieval (spec: `specs/features/graphrag-ingestion.md`)

## Phase 3 — Orchestration

- [ ] LangGraph graph wiring all agents + checkpoints together (`backend/graph/`)
- [ ] FastAPI routes + WebSocket broadcast (`backend/main.py`, `backend/api/v1/`)

## Phase 4 — Frontend (not started, not reviewed against a locked spec yet)
- [~] Next.js 15 scaffold exists from the earlier pass — treat as unreviewed, revisit once backend is solid
- [ ] Everything else — deferred until backend Phase 1-3 are done and specs for frontend behavior are reviewed the same way

## Phase 5 — Infrastructure
- [~] Docker/compose/CI files exist from the earlier pass — revisit once sandbox network fix (Phase 2) and checkpoint types (Phase 2) are implemented, since Dockerfiles/CI need to match

---

## Old checklist (pre-checkpoint, kept for reference only — not current status)

<details>
<summary>Expand: what the discarded first pass had claimed as done</summary>

### Backend
- [x] Scaffold repo structure
- [x] Config + settings
- [x] Database schema + ORM models
- [x] Prompts loader
- [x] Agent: Analyzer
- [x] Agent: Planner (init + next)
- [x] Agent: Coder (init + next)
- [x] Agent: Debugger (summarize + analyzer + coder)
- [x] Agent: Verifier
- [x] Agent: Router
- [x] Agent: Finalyzer + `detect_output_mode()`
- [x] Agent: SubquestionGenerator (init + refine) [DSSTAR+]
- [x] Agent: Writer (init + refine) [DSSTAR+]
- [x] LangGraph graph
- [x] Sandbox executor — Docker + Cloud Run backends
- [x] Catalog scanner — MySQL + file sources, Fernet encryption
- [x] GraphRAG ingestion + retrieval
- [x] Checkpoint / HITL handler
- [x] FastAPI app + all routes

### Frontend
- [x] Next.js 15 scaffold, Clerk auth, API client, WebSocket hook, shared types
- [x] Pages: analyses list/new/detail, catalog, knowledge, reports list/detail
- [x] Components: NavLayout, SessionList, StatusBadge, ActivityFeed, CheckpointPanel, CatalogPage, KnowledgePage, ReportView

### Infrastructure
- [x] Dockerfiles, docker-compose.yml, graphrag/settings.yaml
- [x] GitHub Actions: unit / integration / system workflows

### Tests
- [x] `tests/conftest.py`, fixtures, unit/integration/system test files (37 failing, 71
      passing, 1 error when last run — see checkpoint note above for why these are being
      rewritten rather than patched)

</details>

---

## Pending / Next Steps (still relevant post-checkpoint)

- [ ] Frontend unit tests (`vitest`) — no test files written yet
- [ ] Alembic migration runner (optional — currently using raw SQL init script)
- [ ] Keycloak auth wiring (on-prem deployment path — `AUTH_PROVIDER=keycloak`); also the
      trigger to revisit the Writer's Tailwind CDN vs inline-CSS decision (see
      `specs/agents/writer.md`)
- [ ] Cloud Run executor integration test (requires GCP project)
- [ ] Rate limiting / abuse protection on API routes
- [ ] Playwright E2E browser tests
