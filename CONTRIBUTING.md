# Contributing

## Setup

Follow the [root README](README.md#running-it) to get the backend, frontend, and sandbox
running locally. In short:

```bash
docker build -t dsstar-sandbox:latest ./sandbox
cd backend && cp .env.example .env && uv sync   # fill in .env
cd ../frontend && npm install                    # set VITE_API_BASE / VITE_SUPABASE_*
```

## Before opening a PR

```bash
cd backend && uv run pytest        # must pass
cd frontend && npm run build       # must succeed
```

The frontend has no test suite yet (see `TASKS.md`) — manually exercise whatever you touched.

## Branching & commits

- Branch off `main`, name branches `feat/...`, `fix/...`, or `docs/...` matching the change.
- Keep commits focused; write commit messages that explain *why*, not just *what* (the diff
  already shows what changed).
- Open a PR into `main` — CI (`.github/workflows/ci.yml`) runs the backend test suite
  automatically.

## Scope

- Check `TASKS.md` before starting non-trivial work — it tracks known issues by priority (P0
  security/data-loss risks down to P3 polish) and records past decisions, including deliberate
  deferrals, so you don't redo that analysis.
- If your change closes or introduces a known issue, update `TASKS.md` in the same PR.
- If it changes setup, env vars, an API contract, or the agent graph, update the relevant
  README (`README.md`, `backend/README.md`, `frontend/README.md`) or spec under `specs/` in the
  same PR — the docs are treated as part of the change, not a follow-up.

## Code style

No formatter/linter is enforced on the backend beyond what CI runs (the test suite). The
frontend has `eslint` (`npm run lint`) — note it currently reports pre-existing errors in
vendored `components/ui/` shadcn boilerplate; don't let that block PRs that don't touch those
files, but don't add new lint errors in app code.
