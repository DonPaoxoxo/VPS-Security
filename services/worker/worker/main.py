import asyncio
import logging
import signal
import time

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ssc_core.config import get_settings
from ssc_core.db import AsyncSessionLocal
from worker import health
from worker.checks import (
    check_aapanel_health,
    check_server_connectivity,
    check_website_uptime,
    purge_old_data,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ssc.worker.main")

settings = get_settings()

# AsyncIOScheduler's `shutdown(wait=True)` only blocks for thread/process-pool
# executors — the asyncio executor it uses for coroutine jobs doesn't track
# or wait for in-flight tasks on shutdown at all. Tracked explicitly here so
# a SIGTERM during a job actually waits for it instead of asyncio.run()
# cancelling it mid-flight when main() returns.
_active_job_tasks: set[asyncio.Task] = set()


async def _run_job(name: str, func) -> None:
    """Runs one check function inside its own DB session, logging start,
    success/failure, and duration, and recording the result for the
    healthcheck file (worker/health.py) — independent of whether this run
    raises, so a failing job is visible to `docker compose ps` rather than
    silently swallowed."""
    logger.info("Job %s: starting", name)
    start = time.monotonic()
    try:
        async with AsyncSessionLocal() as db:
            await func(db)
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.exception("Job %s: failed after %.0fms", name, duration_ms)
        health.record_job_result(name, success=False, duration_ms=duration_ms, error=str(exc))
    else:
        duration_ms = (time.monotonic() - start) * 1000
        logger.info("Job %s: succeeded in %.0fms", name, duration_ms)
        health.record_job_result(name, success=True, duration_ms=duration_ms)


def _log_scheduler_event(event) -> None:
    """APScheduler-level safety net: the executor already can't crash the
    loop on a job exception, but this also logs anything that somehow slips
    past `_run_job`'s own try/except (e.g. a bug in `_run_job` itself)."""
    if event.exception:
        logger.error("Scheduler reported job %s raised uncaught: %s", event.job_id, event.exception)
    elif logger.isEnabledFor(logging.DEBUG):
        logger.debug("Scheduler reported job %s executed", event.job_id)


def _add_job(scheduler: AsyncIOScheduler, *, name: str, func, interval_seconds: float) -> None:
    """Registers one job as a real coroutine function — NOT a lambda that
    calls asyncio.create_task(). AsyncIOScheduler's executor runs a plain
    (non-async) callable in a worker thread via run_in_executor, which has no
    running event loop of its own; asyncio.create_task() inside that thread
    then fails with "RuntimeError: no running event loop". Passing an actual
    `async def` here makes AsyncIOScheduler detect it via
    asyncio.iscoroutinefunction and schedule it directly on the scheduler's
    own event loop instead — no executor thread involved at all."""

    async def _job() -> None:
        task = asyncio.current_task()
        if task is not None:
            _active_job_tasks.add(task)
        try:
            await _run_job(name, func)
        finally:
            _active_job_tasks.discard(task)

    _job.__name__ = f"job_{name}"
    health.register_job(name, interval_seconds=interval_seconds)
    scheduler.add_job(
        _job,
        "interval",
        seconds=interval_seconds,
        id=name,
        max_instances=1,  # never run a second overlapping instance of the same job
        coalesce=True,  # if runs were missed (e.g. the loop was blocked), run once on catch-up, not once per missed tick
        misfire_grace_time=30,
    )


async def main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_listener(_log_scheduler_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    _add_job(scheduler, name="website_uptime", func=check_website_uptime, interval_seconds=settings.default_check_interval_seconds)
    _add_job(scheduler, name="server_connectivity", func=check_server_connectivity, interval_seconds=60)
    _add_job(scheduler, name="aapanel_health", func=check_aapanel_health, interval_seconds=120)
    _add_job(scheduler, name="purge_old_data", func=purge_old_data, interval_seconds=24 * 3600)

    scheduler.start()
    logger.info(
        "Worker started: website uptime every %ss, server checks every 60s, aaPanel checks every 120s, retention purge every 24h",
        settings.default_check_interval_seconds,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_shutdown(sig_name: str) -> None:
        logger.info("Received %s, shutting down gracefully", sig_name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _request_shutdown(s.name))
        except NotImplementedError:
            # add_signal_handler isn't available on some platforms (e.g. Windows) —
            # the process still exits on SIGINT via the default KeyboardInterrupt path,
            # it just won't drain scheduler.shutdown(wait=True) first. The container
            # always runs on Linux, where this works correctly.
            logger.warning("Signal handlers unavailable on this platform; shutdown will not wait for in-flight jobs")

    await stop_event.wait()

    scheduler.shutdown(wait=False)  # stops scheduling new runs; see _active_job_tasks note above for why wait=True wouldn't help here
    if _active_job_tasks:
        logger.info("Waiting for %d in-flight job(s) to finish (up to 30s)...", len(_active_job_tasks))
        done, pending = await asyncio.wait(_active_job_tasks, timeout=30)
        if pending:
            logger.warning("%d job(s) did not finish within the shutdown grace period and will be cancelled", len(pending))
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
