# Pinned to a digest, not just the "3.12-slim" tag — a tag can be silently repointed to a
# new image (upstream rebuild, a compromised registry push) with no signal here at all.
# A digest is content-addressed: this exact image, or the build fails closed instead of
# silently pulling something else. Bump deliberately (re-pull the tag, take its new
# digest) rather than letting it drift.
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd app
USER app

WORKDIR /workspace
