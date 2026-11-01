#!/usr/bin/env sh
# Runs database migrations before the API starts serving, so a fresh deploy
# or a `docker compose up -d --build` after a `git pull` never needs a
# separate manual migration step. Idempotent — `alembic upgrade head` is a
# no-op when the schema is already current.
set -e

echo "==> Running database migrations (alembic upgrade head)"
alembic upgrade head

echo "==> Starting API"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
