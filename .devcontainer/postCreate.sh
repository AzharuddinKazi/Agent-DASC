#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

echo "==> Installing backend dependencies"
(cd backend && uv sync)

echo "==> Installing frontend dependencies"
(cd frontend && npm install)

echo "==> Waiting for the Docker daemon"
for i in $(seq 1 30); do
  docker info >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Building the sandbox image (agents/executor.py runs generated code in this)"
docker build -t dsstar-sandbox:latest ./sandbox

echo "==> Installing Claude Code CLI"
npm install -g @anthropic-ai/claude-code

# DSSTAR and the Codespaces-forwarded frontend origin are non-secret — safe to write
# directly. SUPABASE_*/OPENROUTER_API_KEY are NOT written here; set them as Codespaces
# repo secrets (Settings > Secrets and variables > Codespaces) and they land in the
# environment automatically — main.py/llm_router.py read via os.getenv either way.
if [ -n "${CODESPACE_NAME:-}" ]; then
  FRONTEND_ORIGIN="https://${CODESPACE_NAME}-5174.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  BACKEND_ORIGIN="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
else
  FRONTEND_ORIGIN=""
  BACKEND_ORIGIN="http://localhost:8000"
fi

if [ ! -f backend/.env ]; then
  {
    echo "DSSTAR=\"$(pwd)\""
    echo "ALLOWED_ORIGINS=\"http://localhost:5174,http://127.0.0.1:5174${FRONTEND_ORIGIN:+,$FRONTEND_ORIGIN}\""
  } > backend/.env
  echo "Wrote backend/.env with DSSTAR + ALLOWED_ORIGINS."
  echo "Add SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_DB_URL, OPENROUTER_API_KEY"
  echo "as Codespaces secrets, or append them to backend/.env directly."
fi

if [ ! -f frontend/.env ] && [ -n "${SUPABASE_URL:-}" ]; then
  {
    echo "VITE_API_BASE=\"$BACKEND_ORIGIN\""
    echo "VITE_SUPABASE_URL=\"${SUPABASE_URL}\""
    echo "VITE_SUPABASE_ANON_KEY=\"${SUPABASE_ANON_KEY:-}\""
  } > frontend/.env
  echo "Wrote frontend/.env from SUPABASE_URL/SUPABASE_ANON_KEY Codespaces secrets."
fi

echo "==> Done. Start the backend with: cd backend && uv run uvicorn main:app --reload"
echo "==> Start the frontend with:      cd frontend && npm run dev"
echo "==> Log into Claude Code with:    claude"
