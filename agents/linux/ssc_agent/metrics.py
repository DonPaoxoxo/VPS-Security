"""System resource metrics and local service health, using psutil for
portability across kernel versions instead of hand-parsing /proc."""

import os
import socket
import subprocess

import psutil

WATCHED_SERVICES = ["nginx", "apache2", "httpd", "php-fpm", "mysql", "mariadb"]

# aaPanel does not reliably register as a well-formed systemd unit — confirmed
# on 4 production hosts where `systemctl is-active bt` reports "inactive"
# while `bt status` and a live port check both show the panel genuinely up,
# producing a persistent false "service_stopped" alert. Detecting it instead
# by its real BT-Panel process and the port it configured for itself avoids
# depending on a systemd integration aaPanel doesn't actually provide.
AAPANEL_INSTALL_DIR = "/www/server/panel"
AAPANEL_PORT_FILE = "/www/server/panel/data/port.pl"
AAPANEL_PROCESS_MARKER = "BT-Panel"


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


def _read_aapanel_port(port_file: str = AAPANEL_PORT_FILE) -> int | None:
    """Reads aaPanel's own configured port straight from the file it writes
    for itself — ports are frequently changed away from the 8888 default
    during setup, so that can't be assumed."""
    try:
        with open(port_file) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _aapanel_process_running() -> bool:
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if any(AAPANEL_PROCESS_MARKER in part for part in cmdline):
            return True
    return False


def _port_is_listening(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def aapanel_local_status(
    install_dir: str = AAPANEL_INSTALL_DIR,
    port_file: str = AAPANEL_PORT_FILE,
    *,
    process_running: bool | None = None,
    port_open: bool | None = None,
) -> str | None:
    """Returns 'running' / 'stopped' / None (not installed) for aaPanel,
    using its real BT-Panel process and the port it actually configured for
    itself — independent of whether the dashboard can reach its web endpoint
    over the network, and independent of systemctl, which aaPanel does not
    reliably integrate with (see the module-level comment above).

    `process_running` / `port_open` let callers (tests) inject the two
    underlying checks directly instead of requiring a real BT-Panel process
    or a real listening socket on the machine running this code.
    """
    if not os.path.isdir(install_dir):
        return None

    if process_running is None:
        process_running = _aapanel_process_running()

    if port_open is None:
        port = _read_aapanel_port(port_file)
        port_open = port is not None and _port_is_listening(port)

    return "running" if (process_running and port_open) else "stopped"
