"""`schedule` (T-45): recurring tasks defined in `routes/console.py`.

Laravel's model, not taskiq's scheduler: each frequency method sets a cron expression, and
`schedule:run`/`schedule:work` (`commands/schedule.py`) evaluate `schedule.events()` against the
current minute with `croniter.match` (croniter 6.2.4, per the guide and RESEARCH-BASELINE §6).
"""

from __future__ import annotations

import hashlib
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from croniter import croniter

__all__ = ["Schedule", "ScheduleEvent", "schedule"]


@dataclass
class ScheduleEvent:
    kind: str  # "command" | "job" | "call"
    target: Any
    expression: str = "* * * * *"
    overlap_expires_after: int | None = None  # minutes; None = no lock

    # ------------------------------------------------------------ description (schedule:list, tests)

    @property
    def command(self) -> str | None:
        return self.target if self.kind == "command" else None

    @property
    def description(self) -> str:
        if self.kind == "command":
            return str(self.target)
        if self.kind == "job":
            return type(self.target).__name__
        return getattr(self.target, "__qualname__", repr(self.target))

    # ------------------------------------------------------------ fluent frequency builders

    def cron(self, expression: str) -> ScheduleEvent:
        self.expression = expression
        return self

    def every_minute(self) -> ScheduleEvent:
        return self.cron("* * * * *")

    def every_five_minutes(self) -> ScheduleEvent:
        return self.cron("*/5 * * * *")

    def hourly(self) -> ScheduleEvent:
        return self.cron("0 * * * *")

    def daily(self) -> ScheduleEvent:
        return self.cron("0 0 * * *")

    def daily_at(self, time_: str) -> ScheduleEvent:
        hour_s, _, minute_s = time_.partition(":")
        return self.cron(f"{int(minute_s or 0)} {int(hour_s)} * * *")

    def weekly(self) -> ScheduleEvent:
        return self.cron("0 0 * * 0")

    def monthly(self) -> ScheduleEvent:
        return self.cron("0 0 1 * *")

    def without_overlapping(self, expires_after: int = 1440) -> ScheduleEvent:
        self.overlap_expires_after = expires_after
        return self

    # ------------------------------------------------------------ running

    def is_due(self, at: datetime) -> bool:
        return bool(croniter.match(self.expression, at))

    def lock_key(self) -> str:
        digest = hashlib.sha1(f"{self.kind}:{self.description}:{self.expression}".encode()).hexdigest()
        return f"aso:schedule:{digest}"

    async def run(self) -> int:
        """Run this event once, returning an exit code (0 = success)."""
        if self.overlap_expires_after is not None and not await self._acquire_lock():
            return 0  # skipped: a previous run is still holding the lock
        try:
            return await self._dispatch()
        finally:
            if self.overlap_expires_after is not None:
                await self._release_lock()

    async def _dispatch(self) -> int:
        if self.kind == "command":
            return await _run_command_line(str(self.target))
        if self.kind == "job":
            await self.target.dispatch()
            return 0
        result = self.target()
        if hasattr(result, "__await__"):
            await result
        return 0

    async def _acquire_lock(self) -> bool:
        """Mutual exclusion (T-45) through `cache().add()`'s atomic check-and-set: safe even
        across several `schedule:work`/`schedule:run` processes sharing one cache store."""
        from aso.cache import cache

        return await cache().add(self.lock_key(), "1", ttl=(self.overlap_expires_after or 1440) * 60)

    async def _release_lock(self) -> None:
        from aso.cache import cache

        await cache().forget(self.lock_key())


async def _run_command_line(line: str) -> int:
    """`schedule.command("report:send 1 --queue")` -- Laravel's string form: split into a
    command name plus positional/`--option` tokens and run it through `call()` (T-50)."""
    from aso.console.registry import call

    tokens = shlex.split(line)
    if not tokens:
        return 0
    name, rest = tokens[0], tokens[1:]
    params: dict[str, Any] = {}
    positional: list[str] = []
    for token in rest:
        if token.startswith("--"):
            key, _, value = token[2:].partition("=")
            params[f"--{key}"] = value if value else True
        else:
            positional.append(token)

    from aso.console.registry import get as get_registered

    registered = get_registered(name)
    if registered is not None:
        for arg, value in zip(registered.parsed.arguments, positional, strict=False):
            params[arg.name] = value
    return await call(name, params)


class Schedule:
    """`schedule.command/job/call` + `schedule.events()` (T-45)."""

    def __init__(self) -> None:
        self._events: list[ScheduleEvent] = []

    def command(self, command_line: str) -> ScheduleEvent:
        event = ScheduleEvent("command", command_line)
        self._events.append(event)
        return event

    def job(self, job: Any) -> ScheduleEvent:
        event = ScheduleEvent("job", job)
        self._events.append(event)
        return event

    def call(self, fn: Callable[[], Any] | Callable[[], Awaitable[Any]]) -> ScheduleEvent:
        event = ScheduleEvent("call", fn)
        self._events.append(event)
        return event

    def events(self) -> list[ScheduleEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()


schedule = Schedule()
