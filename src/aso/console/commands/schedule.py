"""`schedule:run`, `schedule:work`, `schedule:list` (T-45)."""

from __future__ import annotations

import asyncio
from datetime import datetime

from aso.console.command import Command
from aso.console.registry import register


def _load_schedule():
    from aso.console.registry import load_console_routes
    from aso.console.schedule import schedule
    from aso.foundation.paths import base_path

    load_console_routes(base_path())
    return schedule


class ScheduleRunCommand(Command):
    signature = "schedule:run"
    description = "Run the scheduled commands that are due"

    async def handle(self) -> int:
        count = await run_due_events(self)
        if count == 0:
            self.info("No scheduled commands are ready to run.")
        return 0


class ScheduleWorkCommand(Command):
    signature = "schedule:work"
    description = "Start the schedule worker"

    async def handle(self) -> int:
        self.info("Running scheduled tasks every minute. (Ctrl+C to stop)")
        try:
            while True:
                await run_due_events(self)
                now = datetime.now()
                await asyncio.sleep(60 - now.second - now.microsecond / 1_000_000)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        return 0


class ScheduleListCommand(Command):
    signature = "schedule:list"
    description = "List all scheduled tasks"

    async def handle(self) -> int:
        events = _load_schedule().events()
        if not events:
            self.info("No scheduled tasks have been defined.")
            return 0
        self.table(
            ["Expression", "Description", "Without Overlapping"],
            [[e.expression, e.description, "yes" if e.overlap_expires_after else "no"] for e in events],
        )
        return 0


async def run_due_events(cmd: Command) -> int:
    from aso.log import log

    events = _load_schedule().events()
    now = datetime.now()
    due = [e for e in events if e.is_due(now)]
    for event in due:
        started = datetime.now()
        try:
            log.info("schedule event starting", description=event.description, expression=event.expression)
        except Exception:  # noqa: BLE001 - logging must never break the scheduler
            pass
        try:
            exit_code = await event.run()
        except Exception as exc:  # noqa: BLE001 - one event's crash must not stop the others
            cmd.error(f"{event.description}: {exc}")
            exit_code = 1
        duration = (datetime.now() - started).total_seconds()
        cmd.line(f"{event.description} ... {duration:.2f}s DONE" if exit_code == 0 else f"{event.description} ... FAILED")
        try:
            log.info("schedule event finished", description=event.description, duration_ms=duration * 1000, exit_code=exit_code)
        except Exception:  # noqa: BLE001
            pass
    return len(due)


def register_all() -> None:
    for cls in (ScheduleRunCommand, ScheduleWorkCommand, ScheduleListCommand):
        register(cls, source="framework")
