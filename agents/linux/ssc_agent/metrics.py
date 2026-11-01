"""System resource metrics and local service health, using psutil for
portability across kernel versions instead of hand-parsing /proc."""

import os
import subprocess

import psutil

WATCHED_SERVICES = ["nginx", "apache2", "httpd", "php-fpm", "mysql", "mariadb", "bt"]


def collect_system_metrics() -> dict:
    cpu_pct = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    try:
        load_avg = os.getloadavg()[0]
    except (OSError, AttributeError):
        load_avg = None

    return {
        "cpu_pct": cpu_pct,
        "ram_pct": ram.percent,
        "disk_pct": disk.percent,
        "load_average": load_avg,
        "network_rx_bytes": net.bytes_recv,
        "network_tx_bytes": net.bytes_sent,
    }


def collect_service_status() -> dict[str, str]:
    """Checks `systemctl is-active` for each service we care about. Services
    that aren't installed are omitted rather than reported as failed."""
    statuses: dict[str, str] = {}
    for service in WATCHED_SERVICES:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            continue
        state = result.stdout.strip()
        if state in ("active", "inactive", "failed", "activating", "deactivating"):
            statuses[service] = state
    return statuses


def aapanel_local_status(service_status: dict[str, str]) -> str | None:
    """Returns 'running' / 'stopped' / None (not installed) for aaPanel's own
    service ('bt'), independent of whether the dashboard can reach its web
    endpoint over the network."""
    state = service_status.get("bt")
    if state is None:
        return None
    return "running" if state == "active" else "stopped"
