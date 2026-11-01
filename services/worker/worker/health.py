"""Tracks whether the worker's scheduled jobs are actually succeeding, not
just whether the process is alive. `record_job_result` is called by the live
worker process after every job run and writes a small JSON file; a separate
process (the Docker healthcheck, via `python -m worker.healthcheck`) reads
that file independently, since a healthcheck's `docker exec` spawns a fresh
process that shares no memory with the running worker.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

logger = logging.getLogger("ssc.worker.health")

HEALTH_FILE_PATH = os.environ.get("WORKER_HEALTH_FILE", "/tmp/ssc-worker-health.json")

# A job reporting this many consecutive failures is considered unhealthy
# even if the process itself is still running fine.
CONSECUTIVE_FAILURE_THRESHOLD = int(os.environ.get("WORKER_HEALTH_FAILURE_THRESHOLD", "5"))

_write_failure_already_logged = False


@dataclass
class JobHealth:
    interval_seconds: float
    last_run_at: str | None = None
    last_success_at: str | None = None
    last_duration_ms: float | None = None
    consecutive_failures: int = 0
    last_error: str | None = None


_job_health: dict[str, JobHealth] = {}
_started_at: str = datetime.now(timezone.utc).isoformat()


def register_job(name: str, *, interval_seconds: float) -> None:
    """Called once at scheduler setup for every job, so the health file lists
    every expected job (with `last_run_at: null`) from the moment the worker
    starts — a job that never runs at all is just as unhealthy as one that
    keeps failing, and this makes that detectable too."""
    _job_health[name] = JobHealth(interval_seconds=interval_seconds)
    _write_health_file()


def record_job_result(name: str, *, success: bool, duration_ms: float, error: str | None = None) -> None:
    health = _job_health.setdefault(name, JobHealth(interval_seconds=60))
    now = datetime.now(timezone.utc).isoformat()
    health.last_run_at = now
    health.last_duration_ms = duration_ms
    if success:
        health.last_success_at = now
        health.consecutive_failures = 0
        health.last_error = None
    else:
        health.consecutive_failures += 1
        health.last_error = error
    _write_health_file()


def _write_health_file() -> None:
    payload = {
        "_meta": {
            "started_at": _started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "failure_threshold": CONSECUTIVE_FAILURE_THRESHOLD,
        },
        "jobs": {name: asdict(h) for name, h in _job_health.items()},
    }
    tmp_path = f"{HEALTH_FILE_PATH}.tmp.{os.getpid()}"
    global _write_failure_already_logged
    try:
        with open(tmp_path, "w") as f:
            json.dump(payload, f)
        os.replace(tmp_path, HEALTH_FILE_PATH)  # atomic on POSIX — no reader ever sees a half-written file
        _write_failure_already_logged = False
    except OSError as exc:
        # Must never crash the worker itself over this — but a silent,
        # permanent failure to write here would otherwise just look like
        # "unhealthy: cannot read health file" forever with no indication
        # why. Logged once per failure streak, not on every write, since
        # writes happen roughly every job run (as often as every 60s).
        if not _write_failure_already_logged:
            logger.warning("Cannot write health file %s: %s", HEALTH_FILE_PATH, exc)
            _write_failure_already_logged = True


def evaluate_health_file(path: str = HEALTH_FILE_PATH) -> tuple[bool, str]:
    """Pure function, usable both by the CLI entrypoint and by tests, kept
    free of any process-exit side effects."""
    try:
        with open(path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read health file {path}: {exc}"

    meta = payload.get("_meta", {})
    jobs = payload.get("jobs", {})
    if not jobs:
        return False, "no jobs registered in health file"

    try:
        started_at = datetime.fromisoformat(meta["started_at"])
    except (KeyError, ValueError):
        return False, "health file missing a valid _meta.started_at"

    threshold = meta.get("failure_threshold", CONSECUTIVE_FAILURE_THRESHOLD)
    now = datetime.now(timezone.utc)
    problems = []

    for name, job in jobs.items():
        if job.get("consecutive_failures", 0) >= threshold:
            problems.append(f"{name}: {job['consecutive_failures']} consecutive failures")
            continue

        interval = job.get("interval_seconds", 60)
        grace = max(interval * 3, 300)  # at least 5 minutes, even for fast jobs

        last_run_at = job.get("last_run_at")
        if last_run_at is None:
            age = (now - started_at).total_seconds()
            if age > grace:
                problems.append(f"{name}: never ran within {grace:.0f}s of worker startup")
        else:
            try:
                last_run = datetime.fromisoformat(last_run_at)
            except ValueError:
                problems.append(f"{name}: invalid last_run_at timestamp")
                continue
            age = (now - last_run).total_seconds()
            if age > grace:
                problems.append(f"{name}: last ran {age:.0f}s ago (grace period {grace:.0f}s) — scheduler may be stuck")

    if problems:
        return False, "; ".join(problems)
    return True, "ok"
