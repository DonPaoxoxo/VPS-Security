"""Parses new lines appended to the system auth log since the last run and
extracts SSH login events. Supports the two common log locations/formats
(Debian/Ubuntu's /var/log/auth.log and RHEL/CentOS's /var/log/secure via
journalctl fallback). Read-only; never modifies the source log."""

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

OFFSET_STATE_FILE = "auth_log_offset.json"

_AUTH_LOG_PATHS = ["/var/log/auth.log", "/var/log/secure"]

_FAILED_RE = re.compile(r"Failed password for (invalid user )?(?P<user>\S+) from (?P<ip>[\d.:a-fA-F]+)")
_ACCEPTED_RE = re.compile(r"Accepted (?P<method>\S+) for (?P<user>\S+) from (?P<ip>[\d.:a-fA-F]+)")


@dataclass
class LoginEventRecord:
    occurred_at: datetime
    was_successful: bool
    source_ip: str | None
    account: str | None
    auth_method: str | None


def read_new_login_events(state_dir: str) -> list[LoginEventRecord]:
    import json

    os.makedirs(state_dir, exist_ok=True)
    offset_path = os.path.join(state_dir, OFFSET_STATE_FILE)

    log_path = next((p for p in _AUTH_LOG_PATHS if os.path.exists(p)), None)
    if log_path is None:
        return _read_from_journalctl(state_dir)

    offsets: dict[str, int] = {}
    if os.path.exists(offset_path):
        try:
            with open(offset_path) as f:
                offsets = json.load(f)
        except (OSError, ValueError):
            offsets = {}

    last_offset = offsets.get(log_path, 0)
    file_size = os.path.getsize(log_path)
    if file_size < last_offset:
        last_offset = 0  # log was rotated/truncated

    events: list[LoginEventRecord] = []
    with open(log_path, errors="ignore") as f:
        f.seek(last_offset)
        for line in f:
            event = _parse_line(line)
            if event:
                events.append(event)
        offsets[log_path] = f.tell()

    with open(offset_path, "w") as f:
        json.dump(offsets, f)

    return events


def _parse_line(line: str) -> LoginEventRecord | None:
    now = datetime.now(timezone.utc)  # syslog timestamps lack a year/timezone; agent-receipt time is used instead
    failed = _FAILED_RE.search(line)
    if failed:
        return LoginEventRecord(
            occurred_at=now, was_successful=False, source_ip=failed.group("ip"), account=failed.group("user"),
            auth_method="password",
        )
    accepted = _ACCEPTED_RE.search(line)
    if accepted:
        return LoginEventRecord(
            occurred_at=now, was_successful=True, source_ip=accepted.group("ip"), account=accepted.group("user"),
            auth_method=accepted.group("method"),
        )
    return None


def _read_from_journalctl(state_dir: str) -> list[LoginEventRecord]:
    """Fallback for systems that log only to the systemd journal."""
    import json

    offset_path = os.path.join(state_dir, OFFSET_STATE_FILE)
    cursor = None
    if os.path.exists(offset_path):
        try:
            with open(offset_path) as f:
                cursor = json.load(f).get("journal_cursor")
        except (OSError, ValueError):
            cursor = None

    cmd = ["journalctl", "-u", "sshd", "--no-pager", "-o", "cat"]
    if cursor:
        cmd += ["--after-cursor", cursor]
    else:
        cmd += ["-n", "0"]  # first run: establish a cursor without backfilling history

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []

    events = [e for line in result.stdout.splitlines() if (e := _parse_line(line))]

    try:
        cursor_result = subprocess.run(
            ["journalctl", "-u", "sshd", "--no-pager", "-o", "cat", "--show-cursor", "-n", "1"],
            capture_output=True, text=True, timeout=10,
        )
        new_cursor_line = next((l for l in cursor_result.stdout.splitlines() if l.startswith("-- cursor:")), None)
        if new_cursor_line:
            with open(offset_path, "w") as f:
                json.dump({"journal_cursor": new_cursor_line.split("cursor:", 1)[1].strip()}, f)
    except (OSError, subprocess.SubprocessError):
        pass

    return events
