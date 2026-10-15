"""`Queue`: dispatch orchestration, the generic worker task, and `Queue.fake()` (T-42).

**The `sync` driver does not go through taskiq.** The guide's "How it works" section maps `sync`
onto `taskiq.InMemoryBroker(await_inplace=True)`; this implementation reaches the same observable
behaviour (the job runs immediately, in-process, reusing the caller's database scope, and a
failure propagates to the caller like Laravel's sync connection) without the extra indirection,
since nothing here needs taskiq's message envelope or result backend. See the build report's
"Decisions I made" for the trade-off. The `redis` driver *does* use real taskiq (`drivers.py`).
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from uuid import uuid4

from fastogram.queue import drivers
from fastogram.queue.job import Job


class Queue:
    """`Queue.fake()` + class-level assertions (T-42), and the dispatch entry points."""

    _fake: ClassVar[bool] = False
    _dispatched: ClassVar[list[tuple[type[Job], Job]]] = []

    @classmethod
    def fake(cls) -> None:
        Queue._fake = True
        Queue._dispatched = []

    @classmethod
    def reset(cls) -> None:
        """Test isolation: drop the fake and anything it recorded."""
        Queue._fake = False
        Queue._dispatched = []

    @classmethod
    def assert_dispatched(cls, job_cls: type[Job], check: Any = None) -> None:
        matches = [j for c, j in Queue._dispatched if c is job_cls and (check is None or check(j))]
        assert matches, f"The job [{job_cls.__name__}] was not dispatched."

    @classmethod
    def assert_dispatched_times(cls, job_cls: type[Job], times: int) -> None:
        matches = [j for c, j in Queue._dispatched if c is job_cls]
        assert len(matches) == times, f"The job [{job_cls.__name__}] was dispatched {len(matches)} time(s), expected {times}."

    @classmethod
    def assert_not_dispatched(cls, job_cls: type[Job], check: Any = None) -> None:
        matches = [j for c, j in Queue._dispatched if c is job_cls and (check is None or check(j))]
        assert not matches, f"The job [{job_cls.__name__}] was dispatched."

    @classmethod
    def assert_nothing_dispatched(cls) -> None:
        assert not Queue._dispatched, f"{len(Queue._dispatched)} job(s) were dispatched."

    # ------------------------------------------------------------ dispatch entry points

    @staticmethod
    async def dispatch(job: Job, *, delay: int | timedelta | None = None, queue: str | None = None) -> None:
        job._payload_args()  # validate now; raises JobNotSerializable before anything else
        if Queue._fake:
            Queue._dispatched.append((type(job), job))
            return
        if job.after_commit and _transaction_open():
            from fastogram.database.db import DB

            DB.after_commit(lambda: Queue._deliver(job, delay=delay, queue=queue))
            return
        await Queue._deliver(job, delay=delay, queue=queue)

    @staticmethod
    async def dispatch_sync(job: Job) -> None:
        job._payload_args()
        if Queue._fake:
            Queue._dispatched.append((type(job), job))
            return
        payload = _build_payload(job, queue=job.queue, connection="sync")
        await _run_in_place(job, payload)

    @staticmethod
    async def _deliver(job: Job, *, delay: int | timedelta | None, queue: str | None) -> None:
        name = drivers.driver_name()
        spec = drivers.connection_spec(name)
        queue_name = queue or job.queue
        payload = _build_payload(job, queue=queue_name, connection=name)
        if spec.get("driver", name) == "sync":
            await _run_in_place(job, payload)
            return
        await enqueue_payload(spec, payload, delay=delay)


# ------------------------------------------------------------ payload build / rebuild


def _build_payload(job: Job, *, queue: str, connection: str) -> dict[str, Any]:
    return {
        "uuid": str(uuid4()),
        "job": f"{type(job).__module__}.{type(job).__qualname__}",
        "args": job._payload_args(),
        "attempt": 1,
        "tries": job.tries,
        "backoff": job.backoff,
        "timeout": job.timeout,
        "queue": queue,
        "connection": connection,
        "dispatched_at": datetime.now(UTC).isoformat(),
    }


def _rebuild_job(payload: dict[str, Any]) -> Job:
    """Import the job class by dotted path and rebuild it **without calling `__init__`**
    (`cls.__new__(cls)` + `__dict__.update(args)`), as the T-42 page specifies."""
    module_name, _, class_name = payload["job"].rpartition(".")
    module = importlib.import_module(module_name)
    job_cls = getattr(module, class_name)
    job = job_cls.__new__(job_cls)
    job.__dict__.update(payload["args"])
    return job


def _backoff_for(backoff: int | list[int], attempt: int) -> float:
    """`backoff[attempt - 1]`, the last value repeating past the end of the list (T-42)."""
    if isinstance(backoff, int):
        return backoff
    if not backoff:
        return 0
    index = min(attempt - 1, len(backoff) - 1)
    return backoff[index]


def _transaction_open() -> bool:
    from fastogram.database.scope import current_scope

    try:
        return current_scope().depth > 0
    except RuntimeError:
        return False


async def enqueue_payload(spec: dict[str, Any], payload: dict[str, Any], *, delay: int | timedelta | None = None) -> None:
    """Send an already-built payload to the connection named by `spec` (used by `dispatch()` on
    a non-`sync` connection, and by `queue:retry`)."""
    driver = spec.get("driver")
    if driver == "sync":
        await run_job(payload)
        return
    if driver == "redis":
        await drivers.enqueue_redis(spec, payload, delay=delay)
        return
    raise RuntimeError(f'Unknown queue driver "{driver}".')


# ------------------------------------------------------------ running a job


async def _run_in_place(job: Job, payload: dict[str, Any]) -> None:
    """`sync` driver / `dispatch_sync()`: run `handle()` right now, reusing the caller's scope.

    No retry loop (Laravel's sync connection does not retry either): on failure, `failed()` runs
    and the attempt is recorded in `failed_jobs`, then the exception is re-raised to the caller,
    matching Laravel's `SyncQueue::handleException`.
    """
    try:
        await asyncio.wait_for(job.handle(), timeout=payload["timeout"])
    except Exception as exc:
        await _finalize_failed(job, payload, exc, report_exc=False)
        raise
    # `release()` on `sync` is a no-op: there is no queue to put the job back on.


async def run_job(payload: dict[str, Any]) -> None:
    """The one generic task every real queue connection runs: `fastogram.run_job` (T-42).

    Opens a fresh, request-less database scope (T-30), runs `handle()` with the attempt's
    timeout, and on failure either re-dispatches (with backoff) or finalises the job as failed.
    """
    from fastogram.database.db import DB

    job = _rebuild_job(payload)
    async with DB.scope(fresh=True):
        try:
            await asyncio.wait_for(job.handle(), timeout=payload.get("timeout", 60))
        except Exception as exc:
            await _handle_failure(job, payload, exc)
            return
        if getattr(job, "_released", False):
            await _handle_release(job, payload)


async def _handle_failure(job: Job, payload: dict[str, Any], exc: Exception) -> None:
    attempt = payload["attempt"]
    tries = payload["tries"]
    if attempt < tries:
        delay = _backoff_for(payload["backoff"], attempt)
        from fastogram.queue import drivers as _drivers

        spec = _drivers.connection_spec(payload.get("connection"))
        await enqueue_payload(spec, {**payload, "attempt": attempt + 1}, delay=delay)
        return
    await _finalize_failed(job, payload, exc, report_exc=True)


async def _handle_release(job: Job, payload: dict[str, Any]) -> None:
    attempt = payload["attempt"]
    tries = payload["tries"]
    if attempt >= tries:
        return  # exhausted: Laravel's release() still obeys $tries once it is attempted that many times
    delay = getattr(job, "_release_delay", 0)
    from fastogram.queue import drivers as _drivers

    spec = _drivers.connection_spec(payload.get("connection"))
    await enqueue_payload(spec, {**payload, "attempt": attempt + 1}, delay=delay)


async def _finalize_failed(job: Job, payload: dict[str, Any], exc: Exception, *, report_exc: bool) -> None:
    from fastogram.queue.failed import record_failed_job

    try:
        await job.failed(exc)
    except Exception:  # noqa: BLE001 - failed() must never hide the original failure
        pass
    try:
        await record_failed_job(payload, exc)
    except Exception:  # noqa: BLE001 - never let the failed_jobs write hide the original failure
        pass
    if report_exc:
        from fastogram.exceptions import report

        report(exc)


# ------------------------------------------------------------ after a response / test isolation


async def drain_after_response() -> None:
    """Dispatch every job queued with `Job.dispatch_after_response()` on the current request.

    Not called by this package: see the build report for the exact `foundation/stack.py` hook
    that should call this after the response body has been sent.
    """
    from fastogram import context

    ctx = context.current()
    if ctx is None:
        return
    jobs: list[Job] = ctx.extras.pop("queue.after_response", [])
    for job in jobs:
        await Queue.dispatch(job)


def reset_queue() -> None:
    """Test isolation: `Queue.reset()` plus drop any cached brokers (T-42)."""
    Queue.reset()
    drivers.reset_brokers()
