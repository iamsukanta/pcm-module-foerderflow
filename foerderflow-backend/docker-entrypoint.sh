#!/usr/bin/env bash
set -e

# Apply DB migrations before starting the API (production-safe: idempotent).
echo "[entrypoint] running alembic migrations..."
alembic upgrade head || echo "[entrypoint] WARN: alembic upgrade failed (no migrations yet?)"

if [ "${RUN_SEED:-0}" = "1" ]; then
  echo "[entrypoint] seeding system reference data (Kostenbereiche + TVöD)..."
  python -m app.seeds.system_data || echo "[entrypoint] WARN: system_data seed failed"
  echo "[entrypoint] seeding demo data..."
  python -m app.seeds.demo || echo "[entrypoint] WARN: demo seed failed"
fi

if [ "${SEED_PILOT:-0}" = "1" ]; then
  echo "[entrypoint] seeding pilot org (Freunde alter Menschen e.V.)..."
  python -m app.seeds.system_data || echo "[entrypoint] WARN: system_data seed failed"
  python -m app.seeds.pilot_fam || echo "[entrypoint] WARN: pilot seed failed"
fi

exec "$@"
