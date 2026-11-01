# Reverse-Proxying the API Through aaPanel's Existing Nginx

This VPS already runs aaPanel's Nginx on 80/443 for other sites, plus an "AI Manager" on port
8000 and aaPanel itself. The monitoring stack does **not** run its own reverse proxy or touch
ports 80/443 at all — `services/api` only binds to `127.0.0.1:18080` (loopback-only, set by
`docker-compose.yml`'s `ports: ["127.0.0.1:18080:8000"]`), and aaPanel's Nginx, which you already
manage, proxies a dedicated subdomain to it. Nothing here modifies your existing sites, MySQL, or
the AI Manager.

## Prerequisites

- A subdomain (e.g. `hub.yourdomain.com`) with a DNS A record pointing at this VPS's public IP.
- The monitoring stack already running (`docker compose up -d`, port 18080 bound to loopback —
  confirm with `ss -tlnp | grep 18080`, which should show `127.0.0.1:18080`, not `0.0.0.0:18080`).

## Steps (all inside aaPanel's own UI — nothing here is run by this project)

1. **Website → Add site** in aaPanel. Domain: `hub.yourdomain.com`. No need to create a PHP
   project or document root with real content — this site definition exists only to host the
   Nginx vhost and SSL cert for the proxy.
2. **SSL** tab for that site → issue a Let's Encrypt certificate for `hub.yourdomain.com` (aaPanel
   automates this the same way it does for your other sites) → enable "Force HTTPS".
3. **Reverse Proxy** tab for that site → add a new proxy:
   - Target URL: `http://127.0.0.1:18080`
   - Send Domain: `$host` (or the literal `hub.yourdomain.com`)
   - Enable "Proxy WebSocket" is not required for this API (no websocket endpoints today), but
     leaving it on is harmless.
4. Confirm aaPanel generated something equivalent to this in the site's Nginx config (aaPanel
   writes this for you — shown here so you can verify it, not something to hand-write):

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:18080;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

   The `X-Forwarded-*` headers matter: without them, the API would see every request as coming
   from `127.0.0.1` and as `http://`, which breaks IP-based rate limiting and anything relying on
   scheme. aaPanel's reverse proxy template includes these by default — just confirm they're
   present.
5. Test from outside the VPS: `curl -s https://hub.yourdomain.com/health` should return
   `{"status":"ok"}`.
6. Set `PUBLIC_API_URL=https://hub.yourdomain.com` in `infra/docker/.env` (not
   `http://127.0.0.1:18080` — that's the internal address the proxy uses, never the externally
   reachable one) and restart the API: `docker compose up -d api`.

## Why this approach instead of a bundled reverse proxy container

An earlier version of this deployment plan included a `caddy` container for automatic HTTPS.
That's the right call when nothing else owns ports 80/443 on the host. Here, aaPanel's Nginx
already does and already has a working certificate-issuance flow you're familiar with — adding a
second reverse proxy competing for the same ports would be redundant and risk breaking your
existing sites. Reusing aaPanel's Nginx keeps this stack's footprint to exactly one new thing on
the host: a single loopback-only port.

## What this does NOT touch

- Your existing aaPanel-managed websites, their Nginx vhosts, or their SSL certs.
- MySQL / MariaDB (this stack's own PostgreSQL is entirely separate, in its own Docker network,
  never on the same port, never sharing data).
- The "AI Manager" on port 8000 — this stack's API container also listens on 8000 *inside its own
  container*, which is irrelevant to the host: nothing is published to host port 8000, only to
  host port 18080 on loopback. There is no conflict.
- Firewall/UFW rules. No new rule is needed for the API itself (loopback traffic doesn't cross
  the firewall), and this project does not touch UFW. aaPanel's Nginx already has 80/443 open.
