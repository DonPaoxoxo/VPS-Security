# Agent Enrollment Guide

This is what actually happens when you add a production server through the dashboard's
**Add Server Wizard** — useful if you want to understand it before running a `curl | sudo bash`
command on a server you care about, which you should always be skeptical of.

## What gets installed

- A Python virtualenv at `/opt/ssc-agent/venv`
- The agent code at `/opt/ssc-agent/ssc_agent`
- A systemd unit at `/etc/systemd/system/ssc-agent.service`
- Credentials at `/etc/ssc-agent/credentials.json` (mode `0600`, root-only)
- State files under `/var/lib/ssc-agent` (file-integrity hashes, log read offsets)

Nothing is opened inbound. The agent only makes outbound HTTPS requests to your monitoring hub.

## The enrollment flow

1. In the wizard, you enter the server's name/IP and (optionally) its aaPanel endpoint. This
   creates a `Server` record and immediately requests a **one-time enrollment token**
   (`POST /servers/{id}/enrollment-token`), which expires in 30 minutes by default.
2. The wizard shows an install command containing that token. You run it **as root** on the new
   server. The command downloads `GET /agents/install-bundle.tar.gz` — a tarball of this repo's
   `agents/linux` directory, built at Docker image build time so it can never drift from the code
   actually running on your hub — extracts it, and runs `install.sh` from inside it. That endpoint
   is intentionally unauthenticated (it contains only code, no secrets) since it has to be
   fetchable before the agent has any credentials.
3. `install.sh` sets up the virtualenv and calls `ssc_agent.enroll`, which exchanges the one-time
   token for a **permanent agent API key** (`POST /agents/enroll`). The token is marked used and
   cannot be replayed. The API key is written to `credentials.json` and never shown again by the
   dashboard — if you lose it, generate a new enrollment token and re-run the installer, which
   re-enrolls and issues a fresh key (invalidating the old one).
4. The systemd service starts and immediately:
   - Sends a heartbeat (`POST /agents/heartbeat`) with CPU/RAM/disk/OS and locally observed
     service status (nginx/apache/php-fpm/mysql/aaPanel's own `bt` service).
   - Runs a **read-only** website discovery scan (`POST /agents/discovery`) over the server's
     Nginx/Apache (including aaPanel-managed) virtual host files.
5. The wizard polls until the agent shows "connected," then polls for discovered websites and
   shows them for your review (approve/exclude/reclassify) before anything is monitored.
6. Every 15 minutes after that, discovery re-runs so new sites/subdomains get picked up (nothing
   is deleted from a failed or empty re-scan — see `app/services/discovery.py`). Every 5 minutes,
   the agent ships new SSH login events and file-integrity changes for the paths listed in
   `/etc/ssc-agent/watched-paths.txt` (defaults to `/etc/nginx`, `/etc/apache2`, `/etc/php` — edit
   this file and restart the service to watch application code or other paths).

## Revoking an agent

An agent's credential is independent of every other agent's. Click **Revoke Agent** on that
server's detail page in the dashboard (calls `POST /servers/{id}/agent/revoke`) — every
subsequent request from that agent is rejected immediately, though the systemd service keeps
running on the remote host until you stop it there or re-enroll it with a fresh token.

## What the agent does NOT do

- No inbound ports, ever.
- No remote shell command execution from the dashboard.
- No reading of `wp-config.php` contents or any file that could contain credentials — only
  existence/structure checks (see `ssc_agent/discovery.py::_inspect_document_root`).
- No modifying, deleting, or "fixing" files it finds changed.
