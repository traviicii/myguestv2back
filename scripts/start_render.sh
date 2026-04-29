#!/usr/bin/env bash
set -euo pipefail

RUN_MIGRATIONS_ON_BOOT="${RUN_MIGRATIONS_ON_BOOT:-true}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"

if [[ "${RUN_MIGRATIONS_ON_BOOT}" == "true" ]]; then
  # Fine for a single-instance deployment; disable this when scaling out and run
  # migrations as a one-off release step instead.
  alembic upgrade head
fi

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY}" \
  --log-level "${LOG_LEVEL}"
