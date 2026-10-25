#!/bin/sh
# Container entrypoint: wait for shared DB, ensure schema, then start API.
set -e

echo "[${INSTANCE_ID:-backend}] Waiting for PostgreSQL..."
python - <<'PY'
import asyncio
import os
import sys

import asyncpg

url = os.environ.get("DATABASE_URL", "")
# asyncpg wants postgresql:// not postgresql+asyncpg://
dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
if not dsn:
    print("DATABASE_URL is required", file=sys.stderr)
    sys.exit(1)

async def wait():
    last = None
    for i in range(60):
        try:
            conn = await asyncpg.connect(dsn, timeout=3)
            await conn.execute("SELECT 1")
            await conn.close()
            print("Database is reachable")
            return
        except Exception as exc:
            last = exc
            await asyncio.sleep(1)
    print(f"Database not ready: {last}", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

# Schema: create_all is used because the Alembic revision chain is incomplete.
# Safe for the college demo; replace with `alembic upgrade head` once migrations are fixed.
if [ "${RUN_SCHEMA_INIT:-true}" = "true" ]; then
  echo "[${INSTANCE_ID:-backend}] Ensuring database tables exist..."
  python - <<'PY'
import asyncio
from database.session import create_tables
asyncio.run(create_tables())
print("Schema ready")
PY
fi

# Optional one-time seed — prefer the compose `seed` profile so only one process seeds.
if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[${INSTANCE_ID:-backend}] Seeding demo data..."
  python seed.py || true
fi

echo "[${INSTANCE_ID:-backend}] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
