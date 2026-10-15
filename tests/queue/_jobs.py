"""Module-level `Job` classes for `tests/queue/` (T-42): importable by dotted path, as the
worker rebuilds them (`fastogram.queue.manager._rebuild_job`)."""

from __future__ import annotations

from fastogram.queue import Job

calls: list[dict] = []
attempts: dict[str, int] = {}


def reset() -> None:
    calls.clear()
    attempts.clear()


class EchoJob(Job):
    def __init__(self, value: str) -> None:
        self.value = value

    async def handle(self) -> None:
        session_id = _current_session_id()
        calls.append({"job": "echo", "value": self.value, "session_id": session_id})


class ReleasingJob(Job):
    def __init__(self, key: str) -> None:
        self.key = key

    async def handle(self) -> None:
        attempts[self.key] = attempts.get(self.key, 0) + 1
        calls.append({"job": "release", "key": self.key, "attempt": attempts[self.key]})
        if attempts[self.key] < 2:
            await self.release(delay=0)


class AlwaysFailsJob(Job):
    def __init__(self, label: str) -> None:
        self.label = label

    async def handle(self) -> None:
        calls.append({"job": "fail", "label": self.label})
        raise RuntimeError(f"boom:{self.label}")

    async def failed(self, exc: Exception) -> None:
        calls.append({"job": "failed", "label": self.label, "error": str(exc)})


class FlakyJob(Job):
    def __init__(self, key: str, fail_times: int) -> None:
        self.key = key
        self.fail_times = fail_times

    async def handle(self) -> None:
        attempts[self.key] = attempts.get(self.key, 0) + 1
        calls.append({"job": "flaky", "key": self.key, "attempt": attempts[self.key]})
        if attempts[self.key] <= self.fail_times:
            raise RuntimeError(f"flaky failure {attempts[self.key]}")


class NotSerializableArg:
    pass


class BadJob(Job):
    def __init__(self, thing: object) -> None:
        self.thing = thing

    async def handle(self) -> None:
        pass  # pragma: no cover - dispatch() must raise before this ever runs


def _current_session_id() -> int | None:
    from fastogram.database.scope import current_scope

    try:
        return id(current_scope().session())
    except RuntimeError:
        return None


def make_payload(
    job_cls: type[Job],
    args: dict,
    *,
    tries: int = 1,
    backoff: int | list[int] = 0,
    timeout: int = 60,
    queue: str = "default",
    connection: str = "sync",
    attempt: int = 1,
) -> dict:
    return {
        "uuid": "test-uuid",
        "job": f"{job_cls.__module__}.{job_cls.__qualname__}",
        "args": args,
        "attempt": attempt,
        "tries": tries,
        "backoff": backoff,
        "timeout": timeout,
        "queue": queue,
        "connection": connection,
        "dispatched_at": "2026-01-01T00:00:00+00:00",
    }
