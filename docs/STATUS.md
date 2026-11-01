# Implementation Status

Honest accounting as of the Phase 1 build, the deployment-prep audit, the subsequent adaptation
to the real target VPS, three real runtime/deployment issues found on that VPS after deploying,
and a full API security audit once the backend was confirmed healthy in production. Update this
file as things change — don't let it silently go stale.

## Round 7: full API security audit, with the backend confirmed healthy in production

Audited every router file directly (not from memory) against: anonymous access to sensitive data,
CSRF coverage on every mutation, agent auth, Swagger/OpenAPI exposure, response caching, and
reverse-proxy trust settings now that the API sits behind aaPanel's Nginx.

**Real findings, fixed:**
- **Account-enumeration side channel** in `/auth/login`: a locked-out account returned HTTP 423
  with a distinct message, which only ever fired for a real account — an unauthenticated caller
  could confirm an email has an account by deliberately locking it out and comparing responses to
  a made-up email (which always got a generic 401). Both branches now return the identical 401.
- **TOCTOU race in `POST /auth/setup`**: the "does an owner already exist?" check and the INSERT
  weren't atomic; two concurrent requests could both pass the check before either committed,
  creating two owner accounts. Added migration `0002_singleton_owner_constraint` — a partial
  unique index making a second such row impossible at the database level — plus an `IntegrityError`
  catch in the route so a race surfaces as the same friendly 409 instead of a 500.
- **No reverse-proxy trust configured at all**: with the API now behind aaPanel's Nginx,
  `request.client.host` inside the container was always the proxy's own address for every real
  client — meaning the per-IP rate limiter was (silently) rate-limiting a single shared bucket
  across every real visitor combined, and every audit-log `ip_address` recorded the proxy's
  address instead of the real one. Added `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware`
  (new `TRUSTED_PROXY_IPS` setting, default `*` — safe specifically because the API's published
  port is loopback-only, see the comment in `ssc_core/config.py`) and `TrustedHostMiddleware`
  (new `TRUSTED_HOSTS` setting; `PUBLIC_API_URL`'s hostname is always auto-included). **Caught and
  fixed a real ordering bug of my own while testing this**: middleware order matters in Starlette,
  and my first pass had `ProxyHeadersMiddleware` on the wrong side of `RateLimitMiddleware`, which
  would have made the fix silently not work at all — found by the regression test
  `test_proxy_headers_middleware_is_applied_before_rate_limiter`, not by inspection.
- **Swagger/OpenAPI publicly exposed with no gate**: `/docs`, `/redoc`, `/openapi.json` are now
  `None` (disabled) when `ENVIRONMENT=production`, still available in development.
- **No `Cache-Control` on any response**: added a blanket `no-store, private` via a new
  `NoStoreCacheMiddleware` — nothing this API returns should ever be cached by a browser, a shared
  proxy, or a CDN placed in front of it later.
- **CSRF token compared with plain `==`**: switched to `hmac.compare_digest` as defense-in-depth.

**Reviewed and found already correct** (not just assumed): every router's auth dependencies —
confirmed via a direct grep-and-read of every `@router.*`/`dependencies=`/`Depends(...)` line
across all 12 router files, not from memory. Server inventory, security events, login events,
file-integrity events, IP investigation, incidents, settings, audit logs, alerts, aaPanel, and
domains are all gated at the router level by `Depends(get_current_user)`; every mutating endpoint
additionally requires `Depends(require_csrf)`; agent endpoints require a valid per-server API key
(`require_agent`) with no session-based path at all; `/agents/enroll` requires a valid one-time
token; rate limiting was already in place from an earlier round (10/min login, 5/min setup,
10/min enroll).

**Considered, not implemented**: a Next.js backend-for-frontend (Task 2's "if appropriate"). The
current direct-browser-to-API architecture exposes no privileged credential to JS (the session
cookie is `HttpOnly`; the CSRF token is the one thing deliberately JS-readable, and useless alone)
and CSRF is already covered — a BFF would be strictly more defense-in-depth but is new
infrastructure (session mapping on Vercel's side), not a refactor of existing code, for a
single-owner, non-multi-tenant dashboard. Documented as an optional follow-up in
`infra/deployment/VERCEL_DEPLOYMENT.md` rather than built.

**Tests**: `tests/test_api_security.py` (new, 15 tests) runs the **real** `app.main.app` in a
fresh subprocess per test — proving anonymous access is denied to every sensitive endpoint
group, the login/setup fixes behave identically for the cases that used to differ, docs are
gated correctly in prod vs. dev, `TrustedHostMiddleware` accepts the real
`security-api.yono777hub.com` domain and rejects an arbitrary one, and the proxy-header/rate-limit
ordering is actually correct (not just "both are present"). No live PostgreSQL is required: an
anonymous request is rejected by `get_current_user` before `db.execute()` is ever called, and the
handful of endpoints that do touch the DB regardless (`/agents/enroll`, `/auth/login`'s
enumeration test, `/auth/setup`'s race test) use a mocked session instead of a real connection —
necessary after this round discovered that connecting to a non-listening `localhost:5432` doesn't
fail fast on this Windows dev box, it hangs ~30s, which would have made those tests either slow or
flaky for the wrong reason. Full suite: **56/56 passing** (15 new). Frontend: `npm run typecheck`
and `npm run build` both clean, all 18 routes.

**Not yet verified against the live VPS**: the new migration (`0002_singleton_owner_constraint`)
has not been run against the real PostgreSQL — it applies automatically on the next
`docker compose up -d --build api` (the entrypoint runs `alembic upgrade head` on every start),
but that hasn't happened yet. The `ProxyHeadersMiddleware`/`TrustedHostMiddleware` additions have
not been exercised against a real request actually arriving through aaPanel's Nginx — the tests
here simulate the `X-Forwarded-For`/`Host` headers a correctly-configured proxy would send, per
`AAPANEL_REVERSE_PROXY.md`, but the real proxy's actual headers haven't been inspected.

## Round 6: confirmed the worker healthcheck fix, and why it hadn't taken effect yet

After Round 5, the VPS logs confirmed the scheduler fix itself worked (`website_uptime: succeeded
in 175ms`, `server_connectivity: succeeded in 143ms`, no more event-loop errors) — but the
deployed container's healthcheck was still the old `pgrep -f worker.main`.

**Finding**: the local `infra/docker/docker-compose.yml` already had the correct
`python -m worker.healthcheck` healthcheck from Round 5 — nothing was wrong with the source. The
most likely explanation is the well-known Compose gotcha documented in `DEPLOYMENT.md`'s
"Updating" section as of this round: `docker compose restart <service>` (or `build` alone) does
**not** recreate a container with a changed `docker-compose.yml` — only
`docker compose up -d --build <service>` compares the file against the running container's
config and recreates it if they differ. If the file was uploaded but the worker container was
only restarted/rebuilt rather than recreated, the old healthcheck would keep running indefinitely
even though both the file and the image were already correct.

**Verified/hardened this round**:
- Re-confirmed `services/worker/worker/health.py` and `healthcheck.py` both default to the exact
  same `WORKER_HEALTH_FILE` path, with no environment-variable mismatch possible between the
  writer (the running worker) and the reader (the healthcheck CLI).
- Confirmed the worker's `Dockerfile` has no `USER` directive — the container runs as root
  throughout, so there is no cross-process permission mismatch between the process that writes
  the health file and the process that reads it. Removed the now-dead `procps` package install
  (it existed only to provide `pgrep` for the healthcheck this round replaces for good).
- Added logging (`worker/health.py`) for the one failure mode that used to be silent: if the
  health file genuinely can't be written (e.g. a real permissions problem), it's now logged once
  via `ssc.worker.health` instead of failing invisibly forever.
- Added `tests/test_worker_healthcheck_cli.py` (5 tests): unlike Round 5's tests, which called
  the health-tracking functions directly in-process, these spawn the writer and the
  `python -m worker.healthcheck` reader as **two separate OS subprocesses** communicating only
  through the file on disk — the same relationship Docker's real healthcheck has with the running
  worker container. Covers: healthy after a real success, unhealthy after repeated failures
  (exact job name and count in the output), unhealthy when a job never ran past its grace period,
  unhealthy when no health file exists at all, and recovery back to healthy after a later success.
- Full suite: 41/41 passing (5 new).

**Not yet confirmed**: that `docker compose up -d --build worker` on the actual VPS (not just
re-uploading the file) produces a container whose `docker inspect`'d healthcheck actually matches
— that's the next thing to verify there, with the exact command now in `DEPLOYMENT.md`.

## Round 5: fixed a real worker scheduler crash (`RuntimeError: no running event loop`)

With Postgres/API/migrations all confirmed working, the worker container reported healthy but its
scheduled jobs were failing with `RuntimeError: no running event loop`.

**Root cause**: `services/worker/worker/main.py` registered every job as
`lambda: asyncio.create_task(_run_job(...))`. `AsyncIOScheduler` only schedules a job directly on
its own event loop when it detects the job function as a real coroutine function
(`asyncio.iscoroutinefunction`); a plain `lambda` is not one, so the scheduler ran it the way it
runs any sync callable — inside a threadpool-executor thread via `run_in_executor`. That thread
has no running event loop of its own, so `asyncio.create_task(...)` inside it raised immediately.
Worse, since `_run_job(...)` (the coroutine object) was constructed *before* the failing
`create_task()` call, that coroutine was then garbage-collected unawaited — the exact mechanism
behind "coroutine was never awaited" warnings.

**Fix** (`services/worker/worker/main.py`, rewritten): jobs are now registered as real `async def`
functions via a new `_add_job()` helper — no lambda, no manual `create_task`. This alone was the
actual fix; everything else below builds on top of it:
- `_run_job` now logs start/success/failure with duration, and never lets an exception escape
  (it already caught exceptions before; now it also records the outcome for health tracking).
- `max_instances=1` (already present) plus a new `coalesce=True` and `misfire_grace_time=30` on
  every job, preventing both overlapping runs and a missed-tick pile-up after a slow run.
- An `EVENT_JOB_ERROR`/`EVENT_JOB_EXECUTED` listener logs anything that somehow escapes
  `_run_job` itself.
- Real graceful shutdown: SIGTERM/SIGINT now set a stop event via `loop.add_signal_handler`
  (there wasn't one before — `asyncio.Event().wait()` with no signal handling meant a container
  stop could kill the process mid-job). In-flight job tasks are tracked explicitly in
  `_active_job_tasks` and awaited (up to 30s) before exit — notably, `AsyncIOScheduler.shutdown
  (wait=True)` does **not** actually wait for in-flight coroutine-executor jobs (confirmed by
  reading its behavior directly; `wait=True` only matters for thread/process-pool executors), so
  this tracking is necessary, not redundant.
- New `services/worker/worker/health.py` + `healthcheck.py`: each job run writes its outcome to a
  small JSON file; a separate `python -m worker.healthcheck` process (what Docker's `HEALTHCHECK`
  now runs, replacing the old `pgrep -f worker.main`) reads that file and reports unhealthy if any
  job has 5+ consecutive failures or hasn't run within 3× its interval (minimum 5 minutes grace).
  This directly addresses "detect when scheduled jobs repeatedly fail, rather than reporting
  healthy solely because the process is running" — `pgrep` alone genuinely could not do this.
- `infra/docker/docker-compose.yml`'s `worker` healthcheck updated to use it, with a 90s
  `start_period` so the first 60–120s job intervals get a chance to run before being judged.

**Tests added** (`tests/test_worker_scheduler.py`, 15 tests, all passing — full suite now 36/36):
run the three real check functions (`check_website_uptime`, `check_server_connectivity`,
`check_aapanel_health`) through `_run_job` with a mocked DB session returning zero monitoring
targets (no real network calls); confirmed `_add_job` registers a real coroutine function
(`asyncio.iscoroutinefunction(job.func)` is True — the direct proof of the fix); ran a real
`AsyncIOScheduler` inside a real event loop with a 0.2s-interval job for 0.7s and confirmed it
actually fired (this is the test that would have caught the original bug — under the old code, the
counter would have stayed at 0); captured warnings during that run and asserted none contain "was
never awaited"; confirmed scheduler start/shutdown transitions `state` correctly (and learned
empirically that `shutdown()` defers the state flip to the next loop tick — fixed an incorrect
assumption in the test itself before it passed, see commit history / this file's honesty); and
confirmed the health-file logic correctly flags repeated failures, flags a job that never ran, and
resets `consecutive_failures` to 0 on recovery.

**Validated without a live worker container** (Docker unavailable in this dev environment):
confirmed with real APScheduler + real check functions + mocked DB, not a toy reproduction. **Not
yet confirmed**: the actual `docker compose up -d --build worker` on the VPS, that the healthcheck
command resolves correctly inside the built image's `WORKDIR`, and that a real job (against a real
Postgres with real monitoring targets) completes successfully end-to-end.

## Round 4: fixed a real API networking failure, and corrected a wrong assumption from Round 2

Round 2 (below) put `api` on `ssc-internal` only, reasoning that `internal: true` just blocks
*outbound* traffic and that inbound host-port publishing would be unaffected. On the real VPS,
that turned out to be wrong: Postgres was healthy, `api` itself was healthy (its Docker
`HEALTHCHECK` runs *inside* the container against its own `localhost:8000`, so it says nothing
about host reachability), but `docker compose port api 8000` returned `:0` and
`curl http://127.0.0.1:18080/health` was refused.

**Root cause**: `internal: true` on a Docker network doesn't only remove the default outbound
route — it also adds an isolation rule in the `FORWARD` chain for that network's bridge that
blocks the inbound path host-published-port traffic takes to reach a container on it, even though
`docker inspect`'s `HostConfig.PortBindings` still shows the mapping as configured. A container
whose *only* network is `internal: true` cannot have a working published port at all.

**Fix**: added `api` to `ssc-egress` (the plain bridge network already defined and already used
by `worker` for its own outbound calls) in addition to `ssc-internal`, in
`infra/docker/docker-compose.yml`. This gives `api` a non-isolated network path for its published
port to actually work, while `postgres` remains on `ssc-internal` only, with no published port of
any kind, unaffected by this change. `api`'s own code still makes no outbound internet calls
anywhere — the second network exists solely so the *inbound* published port functions, not
because `api` needs outbound access. Updated `SECURITY_HARDENING.md`'s now-incorrect claim that
"only `worker` needs `ssc-egress`" to explain both reasons `ssc-egress` is used.

**Not yet re-verified on the VPS** (that confirmation is yours to run): after re-uploading
`infra/docker/docker-compose.yml` and running `docker compose up -d --build api`, confirm
`docker compose port api 8000` now returns `0.0.0.0:18080` (or similar, not `:0`) and
`curl http://127.0.0.1:18080/health` returns `{"status":"ok"}`.

## Round 3: fixed a real `docker compose build` failure

Building on the actual Ubuntu VPS (`docker compose build api worker`) failed with:
`ERROR: ../../packages/shared/python is not a valid editable requirement`.

**Root cause**: `services/api/requirements.txt` and `services/worker/requirements.txt` both had a
`-e ../../packages/shared/python` line, intended to install the shared `ssc_core` package as a
side effect of `pip install -r requirements.txt`. pip resolves a relative `-e` path written
*inside* a requirements file against the process's **current working directory at invocation
time** — not against that file's own directory. In both Dockerfiles, `pip install -r
/srv/services/.../requirements.txt` runs while `WORKDIR` is still `/srv` (before it's later
changed to `/srv/services/api` or `/srv/services/worker`), so `../../packages/shared/python`
resolved to a path outside the image entirely. Both Dockerfiles also already ran
`pip install -e /srv/packages/shared/python` (an absolute path) as an explicit prior step — so
the line in each requirements.txt was never necessary in the first place, just silently fragile
until the build context changed enough to actually trigger it.

**Fix**: removed the `-e ../../packages/shared/python` line from both requirements.txt files.
Nothing else changed — the Dockerfiles' existing explicit absolute-path install is sufficient, and
removing the duplicate line means the shared package is now installed exactly once per image
instead of twice. `README.md`'s local-dev instructions were already unaffected: they pass
`-e ../../packages/shared/python` as its own CLI argument (not relying on the file's internal
line), which pip always resolves against the real, unambiguous current working directory.

**Validated without Docker** (unavailable in this dev environment — this must still be confirmed
with an actual `docker compose build api worker` on the VPS): reproduced the exact failure by
running `pip install -r <path>` with a scratch copy of the old broken line from the repo root,
which mirrors the Dockerfile's `WORKDIR /srv` context exactly since `COPY` preserves the same
relative subpaths under `/srv`. Confirmed the error reproduces, then confirmed both *fixed*
requirements.txt files install cleanly from that same working directory, that `ssc_core` imports
correctly afterward, that the FastAPI app still resolves all 38 routes, that the worker still
imports, and that all 23 pytest tests still pass.

## Round 2: adapting to the real VPS (Ubuntu 22.04.5, aaPanel already on 80/443, port 18080 free)

The previous round designed around a bundled Caddy reverse proxy, which assumed nothing else
owned ports 80/443. The real VPS has aaPanel's own Nginx already serving other sites on those
ports, plus an existing "AI Manager" on port 8000. Changed accordingly:

- **Removed the `caddy` service entirely.** The API now publishes to `127.0.0.1:18080` only
  (`ports: ["127.0.0.1:18080:8000"]` in `docker-compose.yml`) — loopback, not `0.0.0.0`, not the
  public IP. aaPanel's existing Nginx reverse-proxies a dedicated HTTPS subdomain to it; see the
  new [AAPANEL_REVERSE_PROXY.md](../infra/deployment/AAPANEL_REVERSE_PROXY.md). This stack never
  touches 80/443, MySQL, or the AI Manager — container-internal port 8000 is irrelevant to the
  host since nothing publishes it there.
- **Found and fixed a real network-isolation bug from the previous round**: `worker` was placed
  only on `ssc-internal`, which is `internal: true` (no outbound internet route) — but `worker`
  is the one service that *needs* outbound internet (website HTTP checks, Telegram API calls,
  aaPanel-instance TCP probes). It would have been unable to do its job. Added a second network,
  `ssc-egress` (plain bridge, no published ports), attached only to `worker`. `postgres` and `api`
  remain on `ssc-internal` only, with no outbound route at all — least privilege, verified by
  reading the resulting network graph rather than assumed.
- **Added a real migration entrypoint**: `services/api/docker-entrypoint.sh` now runs
  `alembic upgrade head` before starting uvicorn, replacing the earlier "run it manually after
  `up`" step. `worker`'s `depends_on: api: condition: service_healthy` uses that as a migration
  gate (worker never calls the API — this ordering exists purely so worker never queries a schema
  that isn't migrated yet on a fresh deploy).
- **Added resource limits** (`deploy.resources.limits`) sized for this host's 4 cores/15GiB,
  shared with aaPanel and the AI Manager: postgres 1 CPU/1GB, api 1 CPU/512MB, worker 0.5 CPU/256MB.
- **Fixed `preflight.sh`'s port-conflict check**, which was previously checking 80/443/8000 as
  if this stack needed them free — it doesn't, and flagging aaPanel's own ports as a "conflict"
  would have been actively misleading. It now checks that 18080 is free (the only port this stack
  needs) and reports 80/443/8000 informationally.
- Verified against the actual source, not assumed: all environment variable names in the new
  compose file (`DATABASE_URL`, `SESSION_SECRET`, `ENVIRONMENT`, `PUBLIC_API_URL`,
  `SESSION_COOKIE_SAMESITE`, `CORS_ALLOWED_ORIGINS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `PERFORMANCE_METRICS_RETENTION_DAYS`, `UPTIME_HISTORY_RETENTION_DAYS`) match field names in
  `packages/shared/python/ssc_core/config.py` exactly — pydantic-settings matches env vars
  case-insensitively against field names by default, confirmed no `env=` alias overrides exist
  that would change this.
- `docker compose config --quiet` was **not** run against the real VPS's Docker Compose (not
  available in this dev environment) — the YAML was instead parsed and validated with PyYAML here
  to confirm structure, and reviewed by hand for compose-schema correctness. Run
  `docker compose config` yourself as step 0 of `DEPLOYMENT.md` before `up`, which will catch
  anything this review missed.

## Audit findings from the previous pass, and what was done about them

| Finding | Severity | Fix |
|---|---|---|
| Agent enrollment-token endpoint hardcoded `https://your-monitoring-hub.example.com` as the install command's API base — every real deployment would have gotten a broken command | **Blocker** | Added `PUBLIC_API_URL` setting (required in production); falls back to the incoming request's URL only in local dev |
| Install command referenced `GET /static/install-agent.sh`, which never existed — no static files were ever mounted, so the one-liner would 404 | **Blocker** | Added `GET /agents/install-bundle.tar.gz`, built from `agents/linux` at Docker image build time (prod) or on-the-fly from the monorepo (dev); install command now downloads + extracts it first |
| No production config validation — the app would start fine with the dev session secret, `CORS_ALLOWED_ORIGINS=*`, etc. | **High** | `Settings._validate_production_config` now refuses to start under `ENVIRONMENT=production` with any insecure default; verified with tests |
| No API rate limiting anywhere (spec explicitly asks for it) | **High** | Added `app/middleware/rate_limit.py`: 10/min on `/auth/login`, 5/min on `/auth/setup`, 10/min on `/agents/enroll`, 300/min default elsewhere, per source IP |
| No SSRF protection on outbound website uptime checks — a vhost `server_name` is attacker-influenceable data, and the worker did an unguarded `httpx.get()` against it with redirects auto-followed | **High** | Added `ssc_core/net_safety.py`: resolves and rejects private/loopback/link-local/metadata-range targets before every website check; redirects are no longer auto-followed (also closes the "unexpected redirect detection" feature gap from the original spec) |
| Retention settings (`performance_metrics_retention_days`, `uptime_history_retention_days`) existed in config but nothing ever purged old rows | **Medium** | Added `purge_old_data` worker job, runs every 24h |
| PostgreSQL port exposure | Checked, not a finding | `docker-compose.yml` has no `ports:` for `postgres` — confirmed still true |
| No HTTPS reverse proxy in the compose stack (spec requires one) | **Medium** | Originally added a bundled `caddy` service; superseded in Round 2 below once the real VPS turned out to already run aaPanel's own Nginx on 80/443 — see Round 2 |
| No log rotation | **Medium** | Added `x-logging` (json-file, 10MB × 5 files) to every compose service |
| No retention/backup tooling | **Medium** | Added `infra/deployment/backup.sh` (dump + optional GPG encryption + optional off-server scp) and `restore.sh` (with a `--target-db` flag for testing restores without touching production) |
| MFA and agent-revocation had API support but no dashboard UI (flagged as a known gap previously) | **Medium** | Both now have real UI: Settings → Account → Enable MFA; server detail page → Revoke Agent |

## What's real and validated locally (this pass)

- Production config validator: tested both the rejection path (insecure defaults under
  `ENVIRONMENT=production`) and the acceptance path (valid overrides) — `tests/test_config_validation.py`.
- SSRF guard: tested against a real public domain (resolves and passes), `localhost`, a raw
  private IP, the cloud metadata address `169.254.169.254`, and an unresolvable hostname —
  `tests/test_net_safety.py`.
- Rate limiter: tested that the 11th request to `/auth/login` within a minute gets HTTP 429 with
  a `Retry-After` header, and that an unmatched path tolerates 50 requests fine —
  `tests/test_rate_limit.py`.
- Install bundle endpoint: exercised over an in-process ASGI client, confirmed it returns a valid
  gzip tarball containing `install.sh`, `requirements.txt`, `ssc-agent.service`, and the full
  `ssc_agent` package.
- Domain discovery, extended: added fixtures for a Laravel app (`artisan` + `composer.json` →
  classified `other`), a reverse-proxied Node.js app (`is_reverse_proxy` indicator fires), and two
  separate vhost config files sharing one document root with different hostnames, confirmed they
  merge into a single discovered website with both hostnames as aliases rather than duplicating —
  `tests/test_discovery_extended.py`.
- 23 pytest tests total, all passing.
- Frontend: `npm run typecheck` and `npm run build` both clean after adding the Revoke Agent
  button and MFA setup flow — all 18 routes still compile.
- `bash -n` syntax-checked `preflight.sh`, `backup.sh`, `restore.sh`; ran `preflight.sh` in a
  non-Linux shell to confirm it degrades to warnings rather than crashing when a given check
  (e.g. `free`, `ss`, `/etc/os-release`) isn't available — it will have all of these on a real
  Ubuntu host.

## What's deliberately stubbed, honestly

- **Reports (PDF export)**: explicitly out of Phase 1 per the spec's own phasing (Phase 3).
- **ObservedIpAddress enrichment** (geolocation/ASN lookup): the table and API exist, nothing
  populates `country`/`city`/`isp`/`asn` yet. Hook up a GeoIP provider before relying on the IP
  Investigation page's location columns.
- **journalctl fallback for auth events**: written (`agents/linux/ssc_agent/auth_log.py`), only
  exercised by code review, not against a real systemd journal.
- **Multi-replica rate limiting**: the limiter is in-memory/per-process, correct for the
  single-VPS deployment this project targets, but would need a shared store (Redis) if the API
  were ever horizontally scaled.

## What has NOT been run against real infrastructure

No Docker, Postgres, or Ubuntu VPS were available in this dev environment. Specifically not yet
verified:

- `docker compose up` for real — Postgres health checks, the migration entrypoint actually
  running cleanly against a live Postgres, container-to-container networking exactly as composed.
  This was partially contradicted once: Round 2 assumed `api` needed no outbound network beyond
  `ssc-internal`, and that assumption broke `api`'s published port on the real VPS (see Round 4).
  Treat anything else in this networking area as similarly worth re-confirming rather than
  trusted outright until you've actually run it.
- The aaPanel reverse-proxy steps in `AAPANEL_REVERSE_PROXY.md` — written from how aaPanel's
  reverse-proxy feature is documented to work, not click-tested against this VPS's actual aaPanel
  version.
- `alembic upgrade head` against a live PostgreSQL database.
- The agent's `install.sh` / systemd unit on an actual Ubuntu host (psutil, `systemctl`,
  `/var/log/auth.log`, `pwd` module — all Linux-only).
- A real Telegram bot receiving a real alert message end-to-end.
- A full Add Server Wizard run against a live agent on a live server, including the new
  tarball-based install flow.
- `backup.sh`/`restore.sh` against a real `docker compose` stack (syntax-checked and logically
  reviewed, not executed against live containers).

**Next concrete step**: run `infra/deployment/preflight.sh` against your actual spare VPS, fix
anything it flags, then work through `infra/deployment/DEPLOYMENT.md` step by step — stopping to
verify each step before moving to the next, exactly as that guide is written to do.
