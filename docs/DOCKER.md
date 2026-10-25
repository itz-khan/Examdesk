# Docker & multi-instance guide (Phase 4)

This stack runs **two identical backend containers** against **one shared PostgreSQL** (and optional Redis), with an nginx proxy acting as a local load balancer (stand-in for AWS ALB). The proxy uses nginx's `least_conn` strategy to send new requests to the backend with fewer active connections.

## Quick start on Windows

1. Install and start Docker Desktop, then install Git.
2. In PowerShell, clone the public demo branch:

   ```powershell
   git clone --branch cloud-render-neon-vercel https://github.com/itz-khan/Examdesk.git
   Set-Location .\Examdesk
   Copy-Item .env.example .env
   ```

3. Edit `.env` and set unique local-only values for `POSTGRES_PASSWORD`,
   `SECRET_KEY`, and `CERT_SECRET_KEY`. To generate a URL-safe random value,
   run `python -c "import secrets; print(secrets.token_urlsafe(32))"` and paste
   the output into one variable. Generate a different value for each secret.
   Do not use the Neon connection string or any cloud credential.
4. Start the database and both backend instances:

   ```powershell
   docker compose up --build -d
   ```

5. Add the demo accounts and sample exam, then start the web UI:

   ```powershell
   docker compose --profile seed run --rm seed
   docker compose --profile frontend up --build -d
   ```

6. Open `http://localhost:3000`. Use the local demo accounts below, or register
   a new local account. To prove which backend handled API traffic, open
   `http://localhost:8080/server-identity`.

This creates a separate local database on the friend's computer. It does not
copy your Neon data or change your hosted app.

## Architecture (local)

```text
Browser / curl
      │
      ▼
 nginx lb :8080  ──►  backend-1 :8000  ──┐
                  └──►  backend-2 :8001  ──┼──►  postgres :5432
                                           └──►  redis :6379 (cache only)
```

Both backends use the same `SECRET_KEY` and `DATABASE_URL`, so JWT auth and exam attempts work no matter which instance handles the request.

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 8080 | `lb` (nginx) | Load-balanced API (prefer this for demos) |
| 8000 | `backend-1` | Direct access to instance 1 |
| 8001 | `backend-2` | Direct access to instance 2 |
| 5432 | `postgres` | Shared database |
| 6379 | `redis` | Optional cache |
| 3000 | `frontend` (profile) | UI (optional) |

## Environment variables

Copy the example file (never commit real secrets):

```bash
cp .env.example .env
# edit POSTGRES_PASSWORD, SECRET_KEY, CERT_SECRET_KEY
```

| Variable | Required | Used by | Notes |
|----------|----------|---------|--------|
| `POSTGRES_DB` | no (default `examdesk`) | postgres, backends | Database name |
| `POSTGRES_USER` | no (default `postgres`) | postgres, backends | DB user |
| `POSTGRES_PASSWORD` | **yes** | postgres, backends | Must match in `DATABASE_URL` |
| `SECRET_KEY` | **yes** | all backends | Must be **identical** on every instance |
| `CERT_SECRET_KEY` | recommended | backends | Certificate HMAC |
| `ALLOWED_ORIGINS` | **yes** | backends | JSON array string for CORS |
| `ENVIRONMENT` | no | backends | `development` / `production` |
| `DEBUG` | no | backends | Prefer `false` in compose |
| `INSTANCE_ID` | set in compose | each backend | `backend-1` / `backend-2` — do not copy the same value |
| `DATABASE_SSL` | set `false` in compose | backends | Local Postgres has no TLS |
| `RUN_SCHEMA_INIT` | default `true` | entrypoint | Creates tables on startup |
| `SEED_ON_START` | default `false` | entrypoint | Prefer the `seed` profile instead |

Compose builds `DATABASE_URL` and `REDIS_URL` for you. You do **not** put host passwords into `docker-compose.yml`.

## Startup procedure

### 1. Prerequisites

- Docker Desktop (or Engine) + Compose v2
- Enough free disk for images (~2 GB)

### 2. Configure secrets

```powershell
Set-Location .\Examdesk
Copy-Item .env.example .env
```

On Windows PowerShell, use:

```powershell
Set-Location .\Examdesk
Copy-Item .env.example .env
```

The example values are for an isolated local demo. Keep `.env` on the
computer running Docker; do not send it to your friend or commit it.

### 3. Build and start core stack

```bash
docker compose up --build -d
```

Starts: postgres, redis, backend-1, backend-2, lb.

### 4. Seed demo users / sample exam

```bash
docker compose --profile seed run --rm seed
```

Demo logins (from seed):

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@examdesk.edu | admin123 |
| Instructor | arjun@examdesk.edu | instructor123 |
| Student | rahul@examdesk.edu | student123 |

### 5. Optional frontend

```bash
docker compose --profile frontend up --build -d
```

UI: http://localhost:3000 — API base URL points at the LB (`http://localhost:8080/api/v1`).

### 6. Verify multi-instance behaviour

```bash
# Distinct identities
curl -s http://localhost:8000/server-identity
curl -s http://localhost:8001/server-identity

# Readiness (what ALB should probe)
curl -s http://localhost:8000/ready
curl -s http://localhost:8080/ready

# Hit the LB several times — both instance IDs should appear
for i in 1 2 3 4 5 6; do
  curl -sI http://localhost:8080/server-identity | grep -i x-instance
done
```

Cross-instance exam state (same as Phase 3): start/save on `:8000`, read on `:8001` — data lives in shared Postgres.

On Windows PowerShell, verify the instances and proxy with:

```powershell
(Invoke-RestMethod http://localhost:8000/server-identity).instance_id
(Invoke-RestMethod http://localhost:8001/server-identity).instance_id
1..8 | ForEach-Object {
    (Invoke-RestMethod http://localhost:8080/server-identity).instance_id
}
```

## Schema / “migrations”

| Step | What happens |
|------|----------------|
| Container start | `entrypoint.sh` waits for Postgres |
| Schema | `create_tables()` (SQLAlchemy `create_all`) when `RUN_SCHEMA_INIT=true` |
| Seed | Separate `seed` profile job |

Alembic files exist but the revision chain is incomplete, so the demo uses `create_all`. For AWS/production later, fix Alembic and switch the entrypoint to `alembic upgrade head`.

## Health checks

| Check | Path | Meaning | Used by |
|-------|------|---------|---------|
| Liveness | `GET /health` | Process is up | Quick ping |
| Readiness | `GET /ready` | Postgres reachable | **Docker HEALTHCHECK**, future **ALB target group** |
| Identity | `GET /server-identity` | Which instance answered | Demo / debugging |
| Header | `X-Instance-ID` | Same identity on every response | Demo / debugging |

Docker marks a backend unhealthy if `/ready` fails. Nginx separately tracks
passive upstream failures with `max_fails`; Docker's health status is not wired
into nginx as an active health check, so do not claim automatic failover.

## Useful commands

```bash
docker compose ps
docker compose logs -f backend-1 backend-2
docker compose restart backend-1          # simulate instance recovery
docker compose stop backend-2             # simulate unhealthy instance
curl -s http://localhost:8080/ready       # LB still works via backend-1
docker compose down                       # stop containers
docker compose down -v                    # stop + DELETE postgres volume
```

## Security notes

- Secrets live in `.env` (gitignored), not in `docker-compose.yml` or images.
- Do not commit real AWS keys, DB passwords, or JWT secrets.
- Change `SECRET_KEY` before any cloud deployment; every instance must share the same value.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Compose exits: `POSTGRES_PASSWORD` / `SECRET_KEY` | Missing `.env` | `cp .env.example .env` and edit |
| Backend unhealthy | DB still starting | Wait for `postgres` healthy; check `docker compose logs backend-1` |
| CORS errors in browser | Origin not in `ALLOWED_ORIGINS` | Add origin as JSON array in `.env` |
| Same `instance_id` on both ports | Misconfigured env | Ensure compose sets `INSTANCE_ID` differently per service |
| Seed fails | Backends not up yet | Start stack first, then run seed profile |
| Port 5432 already in use | Host Postgres running | Stop host Postgres or change compose port mapping |
