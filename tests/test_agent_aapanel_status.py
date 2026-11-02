"""Regression tests for the aaPanel false "service_stopped" alert.

Confirmed on 4 production VPS servers: `systemctl is-active bt` reports
"inactive" while `bt status` and a live port check both show BT-Panel and
BT-Task genuinely running. The fix drops "bt" from WATCHED_SERVICES (so it's
no longer evaluated via systemctl at all) and detects aaPanel instead via its
real BT-Panel process plus the port it configured for itself in
/www/server/panel/data/port.pl.
"""

import socket
import threading

from ssc_agent.metrics import (
    WATCHED_SERVICES,
    _port_is_listening,
    _read_aapanel_port,
    aapanel_local_status,
)


def test_bt_is_no_longer_a_systemctl_watched_service():
    assert "bt" not in WATCHED_SERVICES


def test_aapanel_not_installed_returns_none(tmp_path):
    missing_dir = tmp_path / "no-such-panel"
    assert aapanel_local_status(install_dir=str(missing_dir)) is None


def test_aapanel_running_when_process_and_port_are_both_confirmed(tmp_path):
    install_dir = tmp_path / "panel"
    install_dir.mkdir()

    status = aapanel_local_status(
        install_dir=str(install_dir), process_running=True, port_open=True
    )
    assert status == "running"


def test_aapanel_stopped_when_installed_but_process_is_gone(tmp_path):
    """The exact production scenario: installed, but the panel process is
    not actually running (systemctl's own view is irrelevant here)."""
    install_dir = tmp_path / "panel"
    install_dir.mkdir()

    status = aapanel_local_status(
        install_dir=str(install_dir), process_running=False, port_open=True
    )
    assert status == "stopped"


def test_aapanel_stopped_when_installed_but_port_not_listening(tmp_path):
    install_dir = tmp_path / "panel"
    install_dir.mkdir()

    status = aapanel_local_status(
        install_dir=str(install_dir), process_running=True, port_open=False
    )
    assert status == "stopped"


def test_read_aapanel_port_parses_the_configured_port_file(tmp_path):
    port_file = tmp_path / "port.pl"
    port_file.write_text("7800\n")
    assert _read_aapanel_port(str(port_file)) == 7800


def test_read_aapanel_port_returns_none_when_file_is_missing(tmp_path):
    missing = tmp_path / "does-not-exist.pl"
    assert _read_aapanel_port(str(missing)) is None


def test_read_aapanel_port_returns_none_when_file_content_is_not_a_port(tmp_path):
    port_file = tmp_path / "port.pl"
    port_file.write_text("not-a-number")
    assert _read_aapanel_port(str(port_file)) is None


def test_port_is_listening_detects_a_real_open_and_closed_port():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    stop = threading.Event()

    def accept_loop():
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                conn.close()
            except socket.timeout:
                continue

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    try:
        assert _port_is_listening(port, timeout=1.0) is True
    finally:
        stop.set()
        server.close()
        thread.join(timeout=2)

    assert _port_is_listening(port, timeout=1.0) is False


def test_aapanel_process_detection_matches_real_bt_panel_cmdline(monkeypatch):
    from ssc_agent import metrics

    class _FakeProc:
        def __init__(self, cmdline):
            self.info = {"cmdline": cmdline}

    fake_procs = [
        _FakeProc(["/usr/bin/python3", "/www/server/panel/BT-Panel"]),
        _FakeProc(["nginx: master process"]),
    ]

    monkeypatch.setattr(metrics.psutil, "process_iter", lambda attrs: iter(fake_procs))
    assert metrics._aapanel_process_running() is True


def test_aapanel_process_detection_is_false_when_no_matching_process(monkeypatch):
    from ssc_agent import metrics

    class _FakeProc:
        def __init__(self, cmdline):
            self.info = {"cmdline": cmdline}

    fake_procs = [
        _FakeProc(["nginx: master process"]),
        _FakeProc(["mysqld"]),
    ]

    monkeypatch.setattr(metrics.psutil, "process_iter", lambda attrs: iter(fake_procs))
    assert metrics._aapanel_process_running() is False
