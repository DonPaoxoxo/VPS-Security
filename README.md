# Server Security Center

A self-hosted platform for monitoring your own Ubuntu VPS fleet: server uptime, aaPanel health,
automatic website discovery and classification, performance metrics, security events, login
activity, file integrity, and Telegram alerting — from one private dashboard.

**Status: Phase 1 (core system) implemented, plus a deployment-readiness audit that fixed several
real blockers (broken agent install command, missing production config validation, missing rate
limiting and SSRF protection). See [docs/STATUS.md](docs/STATUS.md) for exactly what's real, what's
tested, and what's still ahead — nothing here has been run against a live Ubuntu VPS yet.**

## Architecture

```
apps/web/            Next.js dashboard (deploy to Vercel)
services/api/        FastAPI backend (deploy on your Ubuntu VPS)
services/worker/      Background monitoring scheduler (deploy on your Ubuntu VPS)
agents/linux/         Lightweight systemd agent for each production server
packages/shared/python/ssc_core   Shared DB models, config, and utilities (api + worker)
infra/docker/          docker-compose.yml for the central hub (Postgres + api + worker;
                       API published to 127.0.0.1 only — no bundled reverse proxy)
infra/deployment/      Deployment guide, agent enrollment guide, aaPanel reverse-proxy guide,
                       hardening checklist, read-only VPS preflight script, backup/restore scripts
tests/                 Backend/agent unit tests (pytest, 23 tests)
```

PostgreSQL never leaves your own VPS and is never exposed on a public port. The frontend talks to
the FastAPI backend directly over HTTPS; the backend is the only thing that talks to Postgres.
Agents only make outbound HTTPS calls to the backend — nothing is ever opened inbound on a
production server for this platform.

## Local development

### Backend + worker

```bash
cd services/api
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate on Linux/macOS
pip install -e ../../packages/shared/python -r requirements.txt
cp ../../infra/docker/.env.example .env           # then edit DATABASE_URL etc. for local use
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
cd services/worker
pip install -e ../../packages/shared/python -r requirements.txt
python -m worker.main
```

Both processes read configuration from environment variables (see
`packages/shared/python/ssc_core/config.py` for the full list) — at minimum set `DATABASE_URL`
to a real PostgreSQL instance; there is no SQLite fallback because the schema uses native
PostgreSQL `UUID`/`JSONB` columns.

### Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL to your local backend
npm run dev
```

Open http://localhost:3000 — the first visit walks you through creating the owner account.

### Tests

```bash
pip install pytest
pytest
```

## Deploying

See [infra/deployment/DEPLOYMENT.md](infra/deployment/DEPLOYMENT.md) for the central-hub setup
(Docker Compose on your spare VPS + Vercel for the frontend), and
[infra/deployment/AGENT_ENROLLMENT.md](infra/deployment/AGENT_ENROLLMENT.md) for adding a
production server via the Add Server Wizard.

## Security

See [infra/deployment/SECURITY_HARDENING.md](infra/deployment/SECURITY_HARDENING.md).
