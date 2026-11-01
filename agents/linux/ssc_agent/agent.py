"""Main agent loop: runs as a systemd service. Sends periodic heartbeats with
resource/service metrics, periodically re-runs read-only website discovery,
and periodically ships file-integrity and auth-log events — all over HTTPS,
authenticated with this server's own revocable API key.
"""

import logging
import platform
import time
from datetime import datetime, timezone

import requests

from ssc_agent.auth_log import read_new_login_events
from ssc_agent.config import STATE_DIR, load_credentials, load_watched_paths
from ssc_agent.discovery import discover_virtual_hosts
from ssc_agent.file_integrity import check_file_integrity
from ssc_agent.metrics import aapanel_local_status, collect_service_status, collect_system_metrics

AGENT_VERSION = "0.1.0"
HEARTBEAT_INTERVAL_SECONDS = 60
DISCOVERY_INTERVAL_SECONDS = 15 * 60
EVENTS_INTERVAL_SECONDS = 5 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s ssc-agent: %(message)s")
logger = logging.getLogger("ssc_agent")


def _headers(api_key: str) -> dict[str, str]:
    return {"X-Agent-Key": api_key, "Content-Type": "application/json"}


def send_heartbeat(creds) -> None:
    metrics = collect_system_metrics()
    service_status = collect_service_status()
    payload = {
        "agent_version": AGENT_VERSION,
        "operating_system": platform.platform(),
        **metrics,
        "service_status": service_status,
        "aapanel_local_status": aapanel_local_status(service_status),
    }
    try:
        resp = requests.post(f"{creds.api_url}/agents/heartbeat", json=payload, headers=_headers(creds.api_key), timeout=15)
        resp.raise_for_status()
        logger.info("Heartbeat sent")
    except requests.RequestException as exc:
        logger.warning("Heartbeat failed: %s", exc)


def run_discovery(creds) -> None:
    started_at = datetime.now(timezone.utc)
    vhosts = discover_virtual_hosts()
    finished_at = datetime.now(timezone.utc)

    payload = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "virtual_hosts": [
            {
                "document_root": v.document_root,
                "web_server": v.web_server,
                "hostnames": v.hostnames,
                "configured_port": v.configured_port,
                "ssl_available": v.ssl_available,
                "redirect_target": v.redirect_target,
                "indicators": v.indicators,
            }
            for v in vhosts
        ],
    }
    try:
        resp = requests.post(f"{creds.api_url}/agents/discovery", json=payload, headers=_headers(creds.api_key), timeout=30)
        resp.raise_for_status()
        logger.info("Discovery submitted: %s", resp.json())
    except requests.RequestException as exc:
        logger.warning("Discovery submission failed: %s", exc)


def run_events(creds) -> None:
    login_events = read_new_login_events(STATE_DIR)
    file_events = check_file_integrity(STATE_DIR, load_watched_paths())

    if not login_events and not file_events:
        return

    payload = {
        "security_events": [],
        "login_events": [
            {
                "occurred_at": e.occurred_at.isoformat(),
                "was_successful": e.was_successful,
                "source_ip": e.source_ip,
                "account": e.account,
                "auth_method": e.auth_method,
            }
            for e in login_events
        ],
        "file_integrity_events": [
            {
                "file_path": e.file_path,
                "change_type": e.change_type,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": e.previous_hash,
                "new_hash": e.new_hash,
                "responsible_account": e.responsible_account,
            }
            for e in file_events
        ],
    }
    try:
        resp = requests.post(f"{creds.api_url}/agents/events", json=payload, headers=_headers(creds.api_key), timeout=20)
        resp.raise_for_status()
        logger.info("Events submitted: %s login, %s file-integrity", len(login_events), len(file_events))
    except requests.RequestException as exc:
        logger.warning("Event submission failed: %s", exc)


def main() -> None:
    creds = load_credentials()
    logger.info("Starting ssc-agent for server %s against %s", creds.server_id, creds.api_url)

    last_discovery = 0.0
    last_events = 0.0

    # Run discovery once immediately on startup so a freshly enrolled server
    # doesn't wait a full interval before the Add Server Wizard's review step
    # has anything to show.
    run_discovery(creds)
    last_discovery = time.monotonic()

    while True:
        send_heartbeat(creds)

        now = time.monotonic()
        if now - last_discovery >= DISCOVERY_INTERVAL_SECONDS:
            run_discovery(creds)
            last_discovery = now
        if now - last_events >= EVENTS_INTERVAL_SECONDS:
            run_events(creds)
            last_events = now

        time.sleep(HEARTBEAT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
