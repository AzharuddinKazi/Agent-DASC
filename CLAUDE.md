# DS-STAR — instructions for Claude Code

FastAPI + LangGraph backend, React/Vite frontend, Supabase, agent pipeline runs LLM-generated
code in a Docker sandbox. See `README.md` and `backend/README.md` for architecture.

## Fresh environment (new Codespace or clone)

`.devcontainer/postCreate.sh` already handles Python/uv, Node, the `dsstar-sandbox` Docker
image, and installs this CLI. Two things it deliberately does NOT do:

1. **`data/` is empty.** Every file in it is gitignored on purpose (`.gitignore`) — none of
   it is secret, it's just large (one file is 470MB) and doesn't belong in git history. If a
   task needs real data present (running the pipeline, testing a domain pack end-to-end),
   run:
   ```
   scripts/fetch_datasets.sh
   ```
   It needs `KAGGLE_USERNAME`/`KAGGLE_KEY` (Kaggle API token — https://www.kaggle.com/settings
   > Account > Create New Token). If those aren't set as Codespaces secrets, the script exits
   with instructions rather than failing silently — read its output. One dataset
   (`hcpcs_level_ii_codes.xlsx`) has no confirmed automated source; the script prints a manual
   download link for it instead of guessing.

2. **`backend/.env` has no real credentials.** `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, `OPENROUTER_API_KEY` are expected as Codespaces
   repo secrets (Settings → Secrets and variables → Codespaces on GitHub), not committed
   anywhere. If a task needs the backend to actually start and none of these are set, say so
   rather than fabricating placeholder values and reporting success.

## Don't re-fetch data/ needlessly

`scripts/fetch_datasets.sh` downloads ~700MB total. Don't run it as a reflex at the start of
every session — only when a task actually needs the data present (e.g. running
`uv run pytest`, which is fully mocked, never needs it).
