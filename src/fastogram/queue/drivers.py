"""Resolving `config/queue.py` connections and the `redis` driver's taskiq broker (T-42, D-011).

`taskiq`/`taskiq-redis` are imported lazily, inside functions, so importing `fastogram.queue`
never requires the `redis` extra. The `sync` driver does not go through taskiq at all: dispatching
on `sync` calls `manager._run_in_place()` directly (see that module's docstring for why).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

_broker_cache: dict[str, Any] = {}
_task_cache: dict[int, Any] = {}


def driver_name() -> str:
    """The configured default connection name (`config/queue.py` -> `default`)."""
    from fastogram.config import config, env

    return config("queue.default") or env("QUEUE_CONNECTION", "sync")


def connection_spec(name: str | None = None) -> dict[str, Any]:
    """The connection's config dict, or a sensible default when `config/queue.py` is missing."""
    from fastogram.config import config, env

    name = name or driver_name()
    connections = config("queue.connections")
    if isinstance(connections, dict) and name in connections:
        return connections[name]
    defaults: dict[str, dict[str, Any]] = {
        "sync": {"driver": "sync"},
        "redis": {
            "driver": "redis",
            "url": env("REDIS_URL", "redis://127.0.0.1:6379/0"),
            "queue": env("REDIS_QUEUE", "default"),
        },
    }
    if name in defaults:
        return defaults[name]
    raise RuntimeError(f'Queue connection "{name}" is not configured. Add it to config/queue.py `connections`.')


def _redis_broker(spec: dict[str, Any]) -> Any:
    try:
        from taskiq_redis import RedisStreamBroker
    except ImportError as exc:
        raise RuntimeError(
            'The "redis" queue driver needs taskiq-redis. Install it with `uv add "fastogram[redis]"`.'
        ) from exc
    url = spec.get("url", "redis://127.0.0.1:6379/0")
    key = f"{url}:{spec.get('queue', 'default')}"
    if key not in _broker_cache:
        _broker_cache[key] = RedisStreamBroker(url=url, queue_name=spec.get("queue", "default"))
    return _broker_cache[key]


def _run_job_task(broker: Any) -> Any:
    """The **one** generic taskiq task, `fastogram.run_job`, registered once per broker."""
    cache_key = id(broker)
    if cache_key not in _task_cache:
        from fastogram.queue.manager import run_job

        @broker.task(task_name="fastogram.run_job")
        async def _run_job(payload: dict[str, Any]) -> None:
            await run_job(payload)

        _task_cache[cache_key] = _run_job
    return _task_cache[cache_key]


def _schedule_source(spec: dict[str, Any]) -> Any:
    from taskiq_redis import ListRedisScheduleSource

    url = spec.get("url", "redis://127.0.0.1:6379/0")
    return ListRedisScheduleSource(url)


async def enqueue_redis(spec: dict[str, Any], payload: dict[str, Any], *, delay: int | timedelta | None = None) -> None:
    """Put `payload` on the Redis stream named by `spec`, or schedule it for later (T-42)."""
    from datetime import UTC, datetime

    broker = _redis_broker(spec)
    task = _run_job_task(broker)
    if delay:
        seconds = delay.total_seconds() if isinstance(delay, timedelta) else float(delay)
        run_at = datetime.now(UTC) + timedelta(seconds=seconds)
        source = _schedule_source(spec)
        await task.kicker().schedule_by_time(source, run_at, payload)
    else:
        await task.kiq(payload)


def reset_brokers() -> None:
    """Drop every broker/task this process has built so far (test isolation)."""
    _broker_cache.clear()
    _task_cache.clear()
