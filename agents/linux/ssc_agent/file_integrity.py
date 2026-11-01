"""Lightweight file integrity monitoring: hashes a configured list of files
and directories, and reports created/modified/deleted/permission/ownership
changes against the previous run. State is a small local JSON file — no
external dependencies, no file content is ever transmitted."""

import hashlib
import json
import os
import pwd
import time
from dataclasses import dataclass

STATE_FILE_NAME = "file_hashes.json"
MAX_FILES_PER_WATCH_PATH = 5000  # safety bound so a huge directory can't stall the agent


@dataclass
class FileIntegrityEvent:
    file_path: str
    change_type: str  # created / modified / deleted / permissions_changed / ownership_changed
    previous_hash: str | None
    new_hash: str | None
    responsible_account: str | None  # best-effort: current file owner, not necessarily who made the change


def _hash_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _owner_name(path: str) -> str | None:
    try:
        uid = os.stat(path).st_uid
        return pwd.getpwuid(uid).pw_name
    except (OSError, KeyError):
        return None


def _snapshot(watched_paths: list[str]) -> dict[str, dict]:
    snapshot: dict[str, dict] = {}
    for base in watched_paths:
        if os.path.isfile(base):
            files = [base]
        elif os.path.isdir(base):
            files = []
            for root, _dirs, names in os.walk(base):
                for name in names:
                    files.append(os.path.join(root, name))
                    if len(files) >= MAX_FILES_PER_WATCH_PATH:
                        break
                if len(files) >= MAX_FILES_PER_WATCH_PATH:
                    break
        else:
            continue

        for path in files:
            try:
                st = os.stat(path)
            except OSError:
                continue
            snapshot[path] = {
                "hash": _hash_file(path),
                "mode": oct(st.st_mode),
                "owner": _owner_name(path),
            }
    return snapshot


def check_file_integrity(state_dir: str, watched_paths: list[str]) -> list[FileIntegrityEvent]:
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, STATE_FILE_NAME)

    previous: dict[str, dict] = {}
    if os.path.exists(state_path):
        try:
            with open(state_path) as f:
                previous = json.load(f)
        except (OSError, json.JSONDecodeError):
            previous = {}

    current = _snapshot(watched_paths)
    events: list[FileIntegrityEvent] = []

    for path, meta in current.items():
        prev_meta = previous.get(path)
        if prev_meta is None:
            events.append(
                FileIntegrityEvent(path, "created", None, meta["hash"], meta["owner"])
            )
            continue
        if prev_meta.get("hash") != meta.get("hash"):
            events.append(
                FileIntegrityEvent(path, "modified", prev_meta.get("hash"), meta.get("hash"), meta["owner"])
            )
        elif prev_meta.get("mode") != meta.get("mode"):
            events.append(FileIntegrityEvent(path, "permissions_changed", None, None, meta["owner"]))
        elif prev_meta.get("owner") != meta.get("owner"):
            events.append(FileIntegrityEvent(path, "ownership_changed", None, None, meta["owner"]))

    for path in set(previous) - set(current):
        events.append(FileIntegrityEvent(path, "deleted", previous[path].get("hash"), None, None))

    with open(state_path, "w") as f:
        json.dump(current, f)

    return events
