# Security Hardening Checklist

## Central hub

- [ ] PostgreSQL has no published port in `docker-compose.yml` (verify: `docker compose port
      postgres 5432` should fail — it's only reachable on the internal `ssc-internal` network).
- [ ] The API is published to `127.0.0.1:18080` only (`docker-compose.yml`'s `ports:` line is
      `"127.0.0.1:18080:8000"`, never a bare `"18080:8000"` which would bind `0.0.0.0`) — verify
      with `ss -tlnp | grep 18080` on the VPS. TLS termination and public exposure happen entirely
      through aaPanel's existing Nginx, which you already manage (see
      [AAPANEL_REVERSE_PROXY.md](AAPANEL_REVERSE_PROXY.md)) — this project does not run its own
      reverse proxy or touch ports 80/443.
- [ ] `SESSION_SECRET` and `POSTGRES_PASSWORD` are long, random, and **not** the defaults in
      `.env.example`.
- [ ] `CORS_ALLOWED_ORIGINS` lists only your actual Vercel domain(s) — not `*`.
- [ ] If the frontend domain differs from the backend domain, `SESSION_COOKIE_SAMESITE=none` is
      set (required for the cookie to be sent cross-site) and the API is served over HTTPS (the
      `Secure` flag is forced automatically whenever `SameSite=None`).
- [ ] MFA (TOTP) is enabled on the owner account — **Settings → Account → Enable MFA** in the
      dashboard now walks through this (scan/enter the secret in an authenticator app, confirm
      with a code). Do this right after your first login.
- [ ] Database backups are copied off the VPS (`infra/deployment/backup.sh`, optionally with
      `GPG_RECIPIENT` for encryption and `REMOTE_DEST` for an off-server copy), and a restore has
      actually been tested with `infra/deployment/restore.sh ... --target-db ssc_restore_test`.
- [ ] The VPS itself follows normal Ubuntu hardening: SSH key-only auth, `fail2ban` or equivalent,
      unattended security upgrades, a firewall (ufw/nftables) allowing only 22/80/443.
- [ ] `ENVIRONMENT=production` is set — the API now refuses to start with the dev session secret,
      a localhost CORS origin, a wildcard CORS origin, an unset `PUBLIC_API_URL`, or the local-dev
      database URL (`ssc_core/config.py::Settings._validate_production_config`). A failed startup
      here is the config telling you something is wrong — fix the named problem, don't bypass it.
- [ ] Rate limiting is active on `/auth/login` (10/min), `/auth/setup` (5/min), and
      `/agents/enroll` (10/min) per source IP, with a generous default elsewhere
      (`app/middleware/rate_limit.py`). It's in-memory and per-process — fine for the single-VPS
      deployment this project targets; note this if you ever run multiple API replicas.
- [ ] Outbound website uptime checks resolve the target hostname and refuse to proceed if it
      points at a private/loopback/link-local/metadata address (`ssc_core/net_safety.py`), so a
      vhost `server_name` pointed at an internal address can't turn the monitoring worker into an
      SSRF probe. Website checks also don't auto-follow redirects, for the same reason.
- [ ] `postgres` sits only on `ssc-internal` (`internal: true`) — no outbound internet route,
      period, and nothing else about it changes this. `api` and `worker` are both also attached
      to `ssc-egress` (plain bridge, no published ports of its own): `worker` because it genuinely
      needs outbound internet (website checks, Telegram, aaPanel TCP probes); `api` purely because
      a container whose *only* network is `internal: true` can't actually be reached through its
      own published port — Docker's isolation rule for that network blocks the inbound forwarding
      path too, not just outbound (confirmed on the real VPS: `docker compose port api 8000`
      returned `:0` and the port was refused until `api` got a non-internal network). `api`'s
      own code still makes no outbound calls anywhere — the second network exists only to make the
      published port reachable, not because `api` needs internet access. If you ever see
      `postgres` needing outbound internet access, that's a sign something is wrong.

## Per-agent

- [ ] Each server's agent credential is independent — compromising one server's agent key does
      **not** grant access to any other server's data (enforced by `require_agent` scoping all
      writes to `agent.server_id`).
- [ ] Enrollment tokens are single-use and expire in 30 minutes (`enrollment_token_ttl_minutes`
      in `ssc_core/config.py`) — don't post one in a public channel "just in case."
- [ ] `/etc/ssc-agent/credentials.json` is mode `0600`, owned by root.
- [ ] The agent's systemd unit runs with `NoNewPrivileges`, `ProtectSystem=full`, `ProtectHome`,
      and `PrivateTmp` (see `agents/linux/ssc-agent.service`) — it still runs as root because it
      needs to read `/var/log/auth.log` and stat files owned by other users, but it cannot gain
      further privileges or write outside the paths it needs.
- [ ] You know what's in `/etc/ssc-agent/watched-paths.txt` on each server and it doesn't include
      anything that changes so often it'll just generate noise (e.g. a cache directory).
- [ ] Revoking a compromised or decommissioned server's agent is one click: that server's detail
      page → **Revoke Agent** (`POST /servers/{id}/agent/revoke`). Requests from it are rejected
      immediately; re-enrolling issues a fresh credential.

## API-layer hardening added in the Round-7 security audit

- [ ] `/docs`, `/redoc`, and `/openapi.json` are disabled when `ENVIRONMENT=production`
      (`app/main.py`) — the full API surface (every route, every field name) is not handed to
      an unauthenticated visitor for no operational benefit. Still available in development.
- [ ] Every response carries `Cache-Control: no-store, private` (`app/middleware/security_headers.py`)
      — nothing this API returns should ever be cached by a browser, a shared proxy, or a CDN.
- [ ] `TrustedHostMiddleware` rejects requests with an unrecognized `Host` header
      (`TRUSTED_HOSTS` env var, defaults to `localhost,127.0.0.1,testserver`; `PUBLIC_API_URL`'s
      own hostname is always trusted automatically).
- [ ] `ProxyHeadersMiddleware` is registered **outer** relative to the rate limiter (verify by
      reading `app/main.py`'s comment and ordering, not just that both are present) — otherwise
      every request appears to come from aaPanel's Nginx itself, collapsing all real clients into
      one shared rate-limit bucket and making audit-log IP addresses meaningless. `TRUSTED_PROXY_IPS`
      (default `*`) is safe only because the API's published port is loopback-only — see the
      comment in `ssc_core/config.py` for the full reasoning, and revisit it if that topology ever
      changes.
- [ ] A locked-out login and a nonexistent-email login now return the *identical* response
      (`app/routers/auth.py`) — the account-lockout path previously returned a distinct HTTP 423
      with a different message, which only ever fired for a real account, letting an
      unauthenticated caller confirm an account exists by deliberately triggering its lockout.
- [ ] Creating the owner account is protected against a race by a database-level constraint, not
      just an application-level check (migration `0002_singleton_owner_constraint` — a partial
      unique index ensuring at most one `users` row can ever have `is_owner = true`), so two
      concurrent `POST /auth/setup` requests can't both succeed. **Run `alembic upgrade head`
      after deploying this — it does not apply itself.**
- [ ] CSRF token comparison uses `hmac.compare_digest` (`app/deps.py::require_csrf`), not a plain
      `==`, as defense-in-depth against timing side-channels.

## Platform-level guarantees already enforced in code (verify, don't just trust)

- [ ] Passwords are hashed with Argon2id (`ssc_core/security.py`), never stored or logged in
      plaintext.
- [ ] Session tokens and agent API keys are stored only as SHA-256 hashes
      (`ssc_core/security.py::hash_token`) — a database leak does not yield usable credentials.
- [ ] Mutating API requests require a per-session CSRF token header in addition to the session
      cookie (`app/deps.py::require_csrf`).
- [ ] Failed login attempts lock the account for `login_lockout_minutes` after
      `login_max_attempts` (`app/routers/auth.py`).
- [ ] The agent never executes remote shell commands sent from the dashboard — there is no such
      endpoint in `app/routers/agents.py`, by design.
