"""`run_worker(queues=...)`: the entry point `fastogram queue:work` will wire up (T-42).

Only the `redis` connection needs a worker process: `sync` jobs run inline at dispatch time. This
best-effort implementation listens on the broker's stream(s) and runs `fastogram.run_job` for
every message; it was written from the taskiq/taskiq-redis docs quoted in RESEARCH-BASELINE §6
without being able to verify the exact worker-loop API against a live broker (the `context7` MCP
tool needed to check taskiq's current API was unreachable this session -- see the build report).
The CLI task should re-check this against taskiq's actual `listen()`/`startup()`/`shutdown()`
signatures before wiring `queue:work` to it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastogram.queue import drivers
from fastogram.queue.manager import run_job


async def run_worker(queues: str | list[str] | None = None, *, concurrency: int = 1) -> None:
    """Run the worker loop for the configured `redis` connection until cancelled.

    `queues` is accepted for forward compatibility with `queue:work --queue=high,default`
    (priority order); this implementation listens to the connection's single configured stream.
    """
    spec = drivers.connection_spec()
    if spec.get("driver") != "redis":
        raise RuntimeError(
            'run_worker() only runs a loop for the "redis" queue driver; "sync" jobs run inline '
            "at dispatch time and need no worker."
        )
    broker = drivers._redis_broker(spec)
    task = drivers._run_job_task(broker)
    await _startup(broker)
    try:
        semaphore = asyncio.Semaphore(max(1, concurrency))
        async for message in _listen(broker):
            await semaphore.acquire()

            async def _run(msg: Any) -> None:
                try:
                    payload = _decode(task, msg)
                    if payload is not None:
                        await run_job(payload)
                finally:
                    semaphore.release()

            asyncio.ensure_future(_run(message))
    finally:
        await _shutdown(broker)


async def _startup(broker: Any) -> None:
    startup = getattr(broker, "startup", None)
    if callable(startup):
        result = startup()
        if hasattr(result, "__await__"):
            await result


async def _shutdown(broker: Any) -> None:
    shutdown = getattr(broker, "shutdown", None)
    if callable(shutdown):
        result = shutdown()
        if hasattr(result, "__await__"):
            await result


async def _listen(broker: Any) -> Any:
    """`async for message in broker.listen()`, the documented taskiq broker API."""
    listen = broker.listen()
    async for message in listen:
        yield message


def _decode(task: Any, message: Any) -> dict[str, Any] | None:
    """Pull the `payload: dict` argument back out of a raw broker message."""
    import json

    data = getattr(message, "data", message)
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    if isinstance(data, str):
        envelope = json.loads(data)
    elif isinstance(data, dict):
        envelope = data
    else:
        return None
    kwargs = envelope.get("kwargs") or {}
    if "payload" in kwargs:
        return kwargs["payload"]
    args = envelope.get("args") or []
    return args[0] if args else None
