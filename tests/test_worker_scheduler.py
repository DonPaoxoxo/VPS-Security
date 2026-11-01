"""Regression tests for the worker scheduler bug: AsyncIOScheduler jobs were
registered as `lambda: asyncio.create_task(...)`, which AsyncIOScheduler runs
in a threadpool-executor thread that has no running event loop, raising
`RuntimeError: no running event loop`. Fixed by registering real `async def`
job functions directly, which AsyncIOScheduler detects and schedules on its
own event loop instead of an executor thread.

All DB access is mocked (`_FakeSession` / `_EmptyResult`) — no real
PostgreSQL is used or required, per "use safe mocked monitoring targets."
"""

import asyncio
import warnings

import pytest

import worker.main as worker_main
from worker import health


class _EmptyResult:
    """Stands in for a SQLAlchemy Result with zero rows, satisfying both
    `.scalars().all()` and `.all()` access patterns used across the three
    real check functions."""

    def scalars(self):
        return self

    def all(self):
        return []


class _FakeSession:
    def __init__(self, execute_raises: Exception | None = None):
        self.committed = False
        self._execute_raises = execute_raises

    async def execute(self, *args, **kwargs):
        if self._execute_raises is not None:
            raise self._execute_raises
        return _EmptyResult()

    async def commit(self):
        self.committed = True


class _FakeSessionContextManager:
    def __init__(self, session: _FakeSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def isolated_health_file(tmp_path, monkeypatch):
    """Every test gets its own health file and a clean in-memory job registry,
    so tests can't see each other's job history."""
    health_file = tmp_path / "worker-health.json"
    monkeypatch.setattr(health, "HEALTH_FILE_PATH", str(health_file))
    health._job_health.clear()
    yield health_file
    health._job_health.clear()


def _patch_session(monkeypatch, fake_session: _FakeSession) -> None:
    monkeypatch.setattr(worker_main, "AsyncSessionLocal", lambda: _FakeSessionContextManager(fake_session))


# --- _run_job against the real check functions, with mocked DB access -----


def test_run_job_executes_real_website_uptime_check_without_error(monkeypatch):
    fake_session = _FakeSession()
    _patch_session(monkeypatch, fake_session)

    asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))

    assert fake_session.committed is True
    job_health = health._job_health["website_uptime"]
    assert job_health.consecutive_failures == 0
    assert job_health.last_success_at is not None


def test_run_job_executes_real_server_connectivity_check_without_runtime_error(monkeypatch):
    fake_session = _FakeSession()
    _patch_session(monkeypatch, fake_session)

    # This is the exact function the original bug broke — a RuntimeError
    # here, if it occurred, would propagate out of asyncio.run() and fail
    # this test.
    asyncio.run(worker_main._run_job("server_connectivity", worker_main.check_server_connectivity))

    job_health = health._job_health["server_connectivity"]
    assert job_health.consecutive_failures == 0


def test_run_job_executes_real_aapanel_health_check_without_runtime_error(monkeypatch):
    fake_session = _FakeSession()
    _patch_session(monkeypatch, fake_session)

    asyncio.run(worker_main._run_job("aapanel_health", worker_main.check_aapanel_health))

    job_health = health._job_health["aapanel_health"]
    assert job_health.consecutive_failures == 0


def test_run_job_catches_exceptions_and_records_failure_without_raising(monkeypatch):
    fake_session = _FakeSession(execute_raises=RuntimeError("simulated DB error"))
    _patch_session(monkeypatch, fake_session)

    # Must NOT raise — _run_job's job is to contain exactly this.
    asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))

    job_health = health._job_health["website_uptime"]
    assert job_health.consecutive_failures == 1
    assert "simulated DB error" in job_health.last_error


def test_repeated_failures_are_detected_as_unhealthy(monkeypatch):
    fake_session = _FakeSession(execute_raises=RuntimeError("down"))
    _patch_session(monkeypatch, fake_session)

    health.register_job("website_uptime", interval_seconds=60)
    for _ in range(health.CONSECUTIVE_FAILURE_THRESHOLD):
        asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))

    healthy, detail = health.evaluate_health_file(str(health.HEALTH_FILE_PATH))
    assert healthy is False
    assert "consecutive failures" in detail


def test_recovery_resets_consecutive_failures(monkeypatch):
    failing_session = _FakeSession(execute_raises=RuntimeError("down"))
    _patch_session(monkeypatch, failing_session)
    asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))
    assert health._job_health["website_uptime"].consecutive_failures == 1

    healthy_session = _FakeSession()
    _patch_session(monkeypatch, healthy_session)
    asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))
    assert health._job_health["website_uptime"].consecutive_failures == 0


# --- Scheduler-level regression tests --------------------------------------


def test_add_job_registers_a_real_coroutine_function_not_a_lambda():
    """Directly proves the fix: job.func must be an async function so
    AsyncIOScheduler schedules it on the event loop instead of a threadpool
    executor (where the original `asyncio.create_task` call failed)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def _dummy_check(db):
        return None

    worker_main._add_job(scheduler, name="test_job", func=_dummy_check, interval_seconds=60)
    job = scheduler.get_job("test_job")

    assert job is not None
    assert asyncio.iscoroutinefunction(job.func), "job.func must be a coroutine function, not a lambda"


def test_scheduler_runs_a_job_end_to_end_inside_a_real_event_loop(monkeypatch):
    """The actual regression test for 'RuntimeError: no running event loop':
    with the original lambda+create_task pattern, this job would never
    successfully increment the counter — AsyncIOScheduler's executor would
    raise RuntimeError in a worker thread, caught internally and reported as
    a job error, and the counter would stay at 0."""
    from apscheduler.events import EVENT_JOB_ERROR
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    fake_session = _FakeSession()
    _patch_session(monkeypatch, fake_session)

    run_count = {"value": 0}

    async def _counting_check(db):
        await db.execute()  # exercises the fake session too
        run_count["value"] += 1

    errors = []

    async def scenario():
        scheduler = AsyncIOScheduler()
        scheduler.add_listener(lambda event: errors.append(event.exception), EVENT_JOB_ERROR)
        worker_main._add_job(scheduler, name="counting_job", func=_counting_check, interval_seconds=0.2)
        scheduler.start()
        try:
            await asyncio.sleep(0.7)  # enough time for the 0.2s-interval job to fire at least twice
        finally:
            scheduler.shutdown(wait=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asyncio.run(scenario())

    unawaited = [w for w in caught if "was never awaited" in str(w.message)]
    assert not unawaited, f"unawaited coroutine warning(s) detected: {unawaited}"
    assert errors == [], f"scheduler reported job error(s): {errors}"
    assert run_count["value"] >= 1, "job never ran — this is the exact symptom of the original bug"


def test_scheduler_startup_and_shutdown():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.base import STATE_STOPPED

    async def _noop(db):
        return None

    async def scenario():
        scheduler = AsyncIOScheduler()
        worker_main._add_job(scheduler, name="noop_job", func=_noop, interval_seconds=60)
        scheduler.start()
        assert scheduler.running is True

        scheduler.shutdown(wait=False)
        # Confirmed empirically: AsyncIOScheduler.shutdown() defers the actual
        # state transition to the next event-loop tick rather than applying
        # it synchronously before returning — `running` only reflects the
        # change after yielding control at least once.
        await asyncio.sleep(0.1)
        assert scheduler.running is False
        assert scheduler.state == STATE_STOPPED

    asyncio.run(scenario())


def test_overlapping_runs_are_prevented_by_max_instances():
    """max_instances=1 (set in _add_job) must be present, or a slow job
    could pile up concurrent executions against the same monitoring
    targets."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def _dummy(db):
        return None

    worker_main._add_job(scheduler, name="test_job", func=_dummy, interval_seconds=60)
    job = scheduler.get_job("test_job")
    assert job.max_instances == 1


# --- Health-file based healthcheck (requirement: detect repeated failures) -


def test_evaluate_health_file_reports_healthy_with_no_failures(monkeypatch):
    fake_session = _FakeSession()
    _patch_session(monkeypatch, fake_session)
    asyncio.run(worker_main._run_job("website_uptime", worker_main.check_website_uptime))

    healthy, detail = health.evaluate_health_file(str(health.HEALTH_FILE_PATH))
    assert healthy is True
    assert detail == "ok"


def test_evaluate_health_file_reports_unhealthy_for_missing_file(tmp_path):
    healthy, detail = health.evaluate_health_file(str(tmp_path / "does-not-exist.json"))
    assert healthy is False


def test_evaluate_health_file_flags_a_job_that_never_ran(monkeypatch):
    # Registered but never executed, and the (fake) worker "started" long
    # enough ago that the grace period has elapsed.
    import json
    from datetime import datetime, timedelta, timezone

    health.register_job("stale_job", interval_seconds=60)
    with open(health.HEALTH_FILE_PATH) as f:
        payload = json.load(f)
    payload["_meta"]["started_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with open(health.HEALTH_FILE_PATH, "w") as f:
        json.dump(payload, f)

    healthy, detail = health.evaluate_health_file(str(health.HEALTH_FILE_PATH))
    assert healthy is False
    assert "stale_job" in detail
