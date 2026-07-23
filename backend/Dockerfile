FROM python:3.12-slim

# docker CLI only — talks to the host daemon via the mounted socket (see agents/executor.py,
# agents/analyzer.py), never runs its own containers. No Docker-in-Docker. docker-cli is only
# a Recommends of docker.io on Debian, not a hard dependency, so it must be named explicitly
# alongside --no-install-recommends or apt silently skips the actual `docker` binary.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io docker-cli \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
