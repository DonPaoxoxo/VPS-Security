"""Validates the worker healthcheck as Docker actually runs it: a fresh,
separate OS process (`python -m worker.healthcheck`) reading a file written
by a different process (the running worker). Everything in
test_worker_scheduler.py exercises the same functions in-process, which
proves the logic is right but not that two independent processes agree on
where the file lives or can actually read/write it — this file proves that
part specifically (requirement: "the healthcheck reads the same health-state
location written by the worker and is accessible with the deployed
container permissions").
"""

import os
import subprocess
import sys
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parent.parent / "services" / "worker"


def _env(tmp_path, **overrides) -> dict:
    env = os.environ.copy()
    env["WORKER_HEALTH_FILE"] = str(tmp_path / "health.json")
    env.update(overrides)
    return env


def _write_in_subprocess(code: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(WORKER_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _run_healthcheck_cli(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "worker.healthcheck"],
        cwd=str(WORKER_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_healthcheck_cli_is_healthy_when_a_separate_process_wrote_success(tmp_path):
    env = _env(tmp_path)

    writer = _write_in_subprocess(
        "from worker import health\n"
        "health.register_job('website_uptime', interval_seconds=60)\n"
        "health.record_job_result('website_uptime', success=True, duration_ms=175.0)\n",
        env,
    )
    assert writer.returncode == 0, writer.stderr
    assert os.path.exists(env["WORKER_HEALTH_FILE"]), "the writer process did not actually create the health file"

    result = _run_healthcheck_cli(env)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "healthy" in result.stdout


def test_healthcheck_cli_is_unhealthy_across_processes_after_repeated_failures(tmp_path):
    env = _env(tmp_path, WORKER_HEALTH_FAILURE_THRESHOLD="3")

    writer = _write_in_subprocess(
        "from worker import health\n"
        "health.register_job('website_uptime', interval_seconds=60)\n"
        "for _ in range(3):\n"
        "    health.record_job_result('website_uptime', success=False, duration_ms=5.0, error='connection refused')\n",
        env,
    )
    assert writer.returncode == 0, writer.stderr

    result = _run_healthcheck_cli(env)
    assert result.returncode == 1
    assert "unhealthy" in result.stderr
    assert "website_uptime" in result.stderr
    assert "3 consecutive failures" in result.stderr


def test_healthcheck_cli_is_unhealthy_when_a_job_never_ran_past_its_grace_period(tmp_path):
    env = _env(tmp_path)

    # register_job writes last_run_at=None; backdate _meta.started_at so the
    # grace period has already elapsed, simulating a scheduler that's stuck.
    writer = _write_in_subprocess(
        "import json\n"
        "from datetime import datetime, timedelta, timezone\n"
        "from worker import health\n"
        "health.register_job('server_connectivity', interval_seconds=60)\n"
        "with open(health.HEALTH_FILE_PATH) as f:\n"
        "    payload = json.load(f)\n"
        "payload['_meta']['started_at'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()\n"
        "with open(health.HEALTH_FILE_PATH, 'w') as f:\n"
        "    json.dump(payload, f)\n",
        env,
    )
    assert writer.returncode == 0, writer.stderr

    result = _run_healthcheck_cli(env)
    assert result.returncode == 1
    assert "server_connectivity" in result.stderr
    assert "never ran" in result.stderr


def test_healthcheck_cli_is_unhealthy_when_no_worker_has_ever_run(tmp_path):
    """No health file exists at all — e.g. right after container creation,
    before start_period has elapsed, or if the worker crashed before writing
    anything."""
    env = _env(tmp_path)  # file deliberately never created

    result = _run_healthcheck_cli(env)
    assert result.returncode == 1


def test_healthcheck_cli_recovers_to_healthy_after_a_later_success(tmp_path):
    env = _env(tmp_path, WORKER_HEALTH_FAILURE_THRESHOLD="2")

    _write_in_subprocess(
        "from worker import health\n"
        "health.register_job('aapanel_health', interval_seconds=120)\n"
        "health.record_job_result('aapanel_health', success=False, duration_ms=5.0, error='timeout')\n"
        "health.record_job_result('aapanel_health', success=False, duration_ms=5.0, error='timeout')\n",
        env,
    )
    assert _run_healthcheck_cli(env).returncode == 1

    _write_in_subprocess(
        "from worker import health\n"
        "health.record_job_result('aapanel_health', success=True, duration_ms=80.0)\n",
        env,
    )
    recovered = _run_healthcheck_cli(env)
    assert recovered.returncode == 0, f"stdout={recovered.stdout!r} stderr={recovered.stderr!r}"
