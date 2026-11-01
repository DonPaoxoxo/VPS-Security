# Deployment Guide

Exact commands for standing up the central hub on your spare Ubuntu VPS — written for the
confirmed environment: Ubuntu 22.04.5, 4 cores, 15GiB RAM, 173GB free, Docker Engine + Compose
already installed, aaPanel's own Nginx already on 80/443, an existing "AI Manager" on port 8000,
port 18080 free. This stack does not touch 80/443, does not touch aaPanel, MySQL, or the AI
Manager, and binds only to `127.0.0.1:18080` on the host.

Nothing in this guide runs automatically. Each step is something you run yourself, when ready.
Read [AGENT_ENROLLMENT.md](AGENT_ENROLLMENT.md) before enrolling a real server (step 12) — know
what the install command does before running it on a server you care about.

## 0. Validate configuration before touching anything live

These are read-only / local-only — safe to run repeatedly, including before the code even exists
on the VPS:

```bash
# Syntax- and schema-validate the compose file (catches typos, bad YAML, unknown keys):
cd infra/docker
docker compose config --quiet && echo "compose file is valid"

# See exactly what would be created, with all variable substitution resolved
# (do this again after filling in .env, to eyeball the final values):
docker compose config
```

## 1. Transfer the code to the VPS

Proposed deployment folder: **`/opt/server-security-center`** — deliberately outside aaPanel's
own `/www` tree (which aaPanel treats as its hosted-sites namespace) so there's no ambiguity about
what this is or risk of aaPanel's own tooling touching it.

Preferred method — clone over SSH, nothing sensitive ever leaves your machine in transit:

```bash
ssh you@your-vps 'sudo mkdir -p /opt/server-security-center && sudo chown $USER:$USER /opt/server-security-center'
ssh you@your-vps
git clone <your-fork-of-this-repo> /opt/server-security-center
cd /opt/server-security-center
```

If you don't have a git remote set up yet and need to copy from this machine instead, use `rsync`
over SSH (encrypted in transit, resumable, and — critically — exclude `.env` so you never
transfer real secrets through a method you haven't deliberately chosen for that):

```bash
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='.next' --exclude='__pycache__' \
  --exclude='.env' --exclude='*.env' \
  "D:/VPS-Security Monitoring/" you@your-vps:/opt/server-security-center/
```

Never `.env` files over rsync/scp even though they're excluded above by habit — type the real
secrets directly on the VPS in step 3 (`nano .env`), or use a secrets manager. A `.env` with real
credentials should never exist outside the VPS it's deployed to and your password manager.

## 2. Install Docker dependencies

Already confirmed installed and running on this VPS — skip. (If verifying a different VPS later:
`infra/deployment/preflight.sh`, read-only, checks this and more.)

## 3. Configure production environment variables

```bash
cd /opt/server-security-center/infra/docker
cp .env.example .env
chmod 600 .env   # contains secrets once filled in — owner-read-only
nano .env
```

Fill in: `POSTGRES_PASSWORD`, `SESSION_SECRET` (32+ random chars — generate with
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`), `PUBLIC_API_URL` (the HTTPS
subdomain from step 7, e.g. `https://hub.yourdomain.com` — **not** `http://127.0.0.1:18080`),
`CORS_ALLOWED_ORIGINS` (your Vercel domain — can be a placeholder for now, updated in step 11),
and `SESSION_COOKIE_SAMESITE=none` (required since Vercel and this VPS are different domains).

The API **refuses to start** (enforced by `ENVIRONMENT=production`, set in `docker-compose.yml`
itself, not something you set here) if any of these are left as insecure defaults — that's
intentional config validation, not a bug to work around. Re-run `docker compose config` now to
confirm the substituted values look right.

## 4. Build and launch

```bash
docker compose up -d --build
docker compose ps
```

Expected: `postgres` becomes `healthy` first, then `api` builds, runs its migration entrypoint,
and becomes `healthy`, then `worker` starts (it waits on `api` being healthy — not because it
calls the API, but as a signal that migrations have finished; see the comment in
`docker-compose.yml`).

Database migrations run **automatically** on every `api` container start
(`services/api/docker-entrypoint.sh` runs `alembic upgrade head` before starting uvicorn) — no
separate manual migration step, and it's a no-op when the schema is already current.

## 5. Confirm actual health, not just "containers running"

```bash
docker compose ps                                   # all three: running/healthy
curl -s http://127.0.0.1:18080/health                # {"status":"ok"} — from ON the VPS
docker compose logs api | tail -30                   # look for "Running database migrations" then "Starting API", no tracebacks
docker compose logs worker | tail -30                # look for "Worker started: website uptime every..."
ss -tlnp | grep 18080                                # must show 127.0.0.1:18080, NOT 0.0.0.0:18080
docker exec $(docker compose ps -q postgres) pg_isready -U ssc   # "accepting connections"
```

Do not consider this deployed until every line above actually prints what's expected — the
containers reporting "running" is necessary but not sufficient.

## 6. Create the owner account

```bash
curl -s http://127.0.0.1:18080/auth/setup-required       # {"setup_required": true}
curl -s -X POST http://127.0.0.1:18080/auth/setup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@yourdomain.com","password":"<a long passphrase, 12+ chars>","display_name":"You"}'
```

(Or wait and do this through the dashboard once step 11 is done — both call the same endpoint.)
Then enable MFA immediately: **Settings → Account → Enable MFA** once logged in.

## 7. Reverse-proxy a subdomain through aaPanel's existing Nginx

See [AAPANEL_REVERSE_PROXY.md](AAPANEL_REVERSE_PROXY.md) — this is done entirely inside aaPanel's
own UI, not by anything in this repo. Confirm `https://hub.yourdomain.com/health` works from
outside the VPS before moving on.

## 8. View service logs

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs --tail=200 postgres
```

Logs are capped at 10MB × 5 files per service (`x-logging` in `docker-compose.yml`) — they won't
fill the disk silently.

## 9. Deploy the frontend to Vercel

```bash
cd apps/web
vercel link
vercel env add NEXT_PUBLIC_API_URL   # https://hub.yourdomain.com (the aaPanel-proxied subdomain)
vercel deploy --prod
```

Once you have the real Vercel URL, go back to the VPS's `.env` and set `CORS_ALLOWED_ORIGINS` to
it exactly, then `docker compose up -d api`.

## 10. Enroll the first test server

In the dashboard: **Servers → Add Server**, fill in the wizard's step 1, then run the install
command it shows you **as root** on that server. See
[AGENT_ENROLLMENT.md](AGENT_ENROLLMENT.md) for exactly what that command does before you run it.
Note: this is a *different* server than the monitoring hub — don't enroll the hub VPS itself
unless you also want to monitor it as a target, which is fine to do but is a separate decision.

## 11. Test domain discovery

Runs automatically on agent connect and every 15 minutes after. To watch it happen:

```bash
# On the monitored server, as root:
journalctl -u ssc-agent -f
```

Confirm in the dashboard: **Domain Inventory** shows the discovered site(s) once approved in the
wizard's review step, correctly tagged WordPress/Static/Other.

## 12. Test Telegram notifications

Set the bot token/chat ID in **Settings → Telegram Notifications**, then trigger a real event —
stop a monitored site's web server, or `systemctl stop ssc-agent` on a test server — and wait up
to a minute for the next check cycle. Confirm a message arrives, an incident appears under
**Incidents & Alerts**, and recovering the service produces a recovery message and closes it.

## Backups

```bash
bash infra/deployment/backup.sh
# With encryption + off-server copy:
GPG_RECIPIENT=you@yourdomain.com REMOTE_DEST=you@offsite-host:/backups/ssc bash infra/deployment/backup.sh

# Cron (daily at 02:00):
0 2 * * * cd /opt/server-security-center && GPG_RECIPIENT=you@yourdomain.com REMOTE_DEST=you@offsite-host:/backups/ssc bash infra/deployment/backup.sh >> /var/log/ssc-backup.log 2>&1

# Test a restore periodically (into a scratch DB, never production):
bash infra/deployment/restore.sh /var/backups/ssc/ssc-20260101-020000.sql.gz.gpg --target-db ssc_restore_test
```

## Updating

```bash
cd /opt/server-security-center
git pull
docker compose up -d --build   # migrations run automatically as part of the api container starting
```

**`docker compose up -d --build` — not `restart`, not just `build`.** `docker compose restart
<service>` restarts the *existing* container with whatever config it was created with; it does
**not** pick up changes to `docker-compose.yml` itself (healthcheck, environment, networks,
resource limits — none of it). `docker compose build <service>` alone only rebuilds the image,
it doesn't recreate the running container either. Only `docker compose up -d --build` compares
the current `docker-compose.yml` against the running container's config and recreates it if
they differ. If you've ever uploaded a `docker-compose.yml` change and a setting didn't seem to
take effect, this is almost always why — confirm what a container is actually running with:

```bash
docker inspect --format='{{json .Config.Healthcheck}}' $(docker compose ps -q worker)
```

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| `api` container restarts in a loop | Insecure/missing production config, or a migration failure | `docker compose logs api` — the config validator names exactly which setting is wrong; a migration error shows the alembic traceback |
| `curl http://127.0.0.1:18080/health` fails from the VPS itself | `api` not actually running/healthy yet, or wrong port | `docker compose ps`; `ss -tlnp \| grep 18080` |
| `https://hub.yourdomain.com/health` fails but `127.0.0.1:18080` works | aaPanel reverse proxy misconfigured, or DNS not pointing here | Re-check the aaPanel site's reverse-proxy target and the domain's DNS record |
| Frontend gets CORS errors | `CORS_ALLOWED_ORIGINS` doesn't match the Vercel URL exactly (scheme+host) | Re-check the value, `docker compose up -d api` after fixing |
| Login works but every POST 403s | `SESSION_COOKIE_SAMESITE` not `none` with a cross-domain frontend | Set it, restart `api` |
| Agent never shows "connected" | Enrollment token expired (30 min) before `install.sh` ran | Issue a new token from the wizard and retry |
| `worker` never starts | It's waiting on `api`'s healthcheck, and `api` isn't healthy yet | Fix `api` first (see above); `worker` will start automatically once `api` reports healthy |
| Port 18080 reachable from outside the VPS | `ports:` line doesn't actually say `127.0.0.1:18080:8000` | Check `docker compose config`'s resolved output; a bare `"18080:8000"` binds `0.0.0.0` instead — not what this file specifies, but double-check if you've edited it |

## Rollback

```bash
# Roll back to the previous image/code without touching data:
git checkout <previous-commit>
docker compose up -d --build

# Roll back a bad migration (rare — most migrations here are additive):
docker compose exec api alembic downgrade -1

# Full disaster recovery: restore the last known-good backup (see Backups above),
# then docker compose up -d --build on the matching code revision.
```
