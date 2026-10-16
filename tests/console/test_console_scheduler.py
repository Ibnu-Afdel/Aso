"""`schedule` (T-45): frequencies, due-ness, `without_overlapping`, and the `schedule:*` commands."""

from __future__ import annotations

from datetime import datetime

from aso.console.schedule import Schedule


def test_frequency_helpers_set_the_expected_cron_expression() -> None:
    s = Schedule()
    assert s.command("a").every_minute().expression == "* * * * *"
    assert s.command("b").every_five_minutes().expression == "*/5 * * * *"
    assert s.command("c").hourly().expression == "0 * * * *"
    assert s.command("d").daily().expression == "0 0 * * *"
    assert s.command("e").daily_at("02:30").expression == "30 2 * * *"
    assert s.command("f").weekly().expression == "0 0 * * 0"
    assert s.command("g").monthly().expression == "0 0 1 * *"
    assert s.command("h").cron("*/15 * * * *").expression == "*/15 * * * *"


def test_is_due_matches_the_cron_expression() -> None:
    s = Schedule()
    event = s.command("session:prune").daily()
    assert event.is_due(datetime(2026, 1, 1, 0, 0))
    assert not event.is_due(datetime(2026, 1, 1, 0, 1))
    assert not event.is_due(datetime(2026, 1, 1, 12, 0))


def test_events_returns_every_registered_event_and_clear_empties_it() -> None:
    s = Schedule()
    s.command("a").daily()
    s.job(object()).hourly()
    s.call(lambda: None).every_minute()
    assert len(s.events()) == 3
    s.clear()
    assert s.events() == []


async def test_command_event_runs_through_call() -> None:
    from aso.console import Command, call_output
    from aso.console.registry import register, reset_registry

    class PingCommand(Command):
        signature = "ping:sched"
        description = ""

        async def handle(self) -> int:
            self.info("pong")
            return 0

    register(PingCommand)
    try:
        s = Schedule()
        event = s.command("ping:sched").every_minute()
        exit_code = await event.run()
        assert exit_code == 0
        assert "pong" in call_output()
    finally:
        reset_registry()


async def test_command_event_with_laravel_string_arguments() -> None:
    from aso.console import Command
    from aso.console.registry import register, reset_registry

    seen: dict[str, object] = {}

    class ReportCommand(Command):
        signature = "report:sched {user_id} {--queue}"
        description = ""

        async def handle(self) -> int:
            seen["user_id"] = self.argument("user_id")
            seen["queue"] = self.option("queue")
            return 0

    register(ReportCommand)
    try:
        s = Schedule()
        event = s.command("report:sched 1 --queue")
        await event.run()
        assert seen == {"user_id": "1", "queue": True}
    finally:
        reset_registry()


async def test_job_event_dispatches_the_job() -> None:
    class FakeJob:
        def __init__(self) -> None:
            self.dispatched = False

        async def dispatch(self) -> None:
            self.dispatched = True

    job = FakeJob()
    s = Schedule()
    event = s.job(job).hourly()
    await event.run()
    assert job.dispatched is True


async def test_call_event_awaits_an_async_callable() -> None:
    calls = []

    async def heartbeat() -> None:
        calls.append(1)

    s = Schedule()
    event = s.call(heartbeat).every_minute()
    await event.run()
    assert calls == [1]


async def test_without_overlapping_skips_a_second_concurrent_run() -> None:
    from aso.cache import flush_all

    runs = []

    async def slow() -> None:
        runs.append(1)

    s = Schedule()
    event = s.call(slow).every_minute().without_overlapping(expires_after=60)
    try:
        await event._acquire_lock()  # simulate: a previous run is still holding the lock
        await event.run()
        assert runs == []  # skipped
    finally:
        await event._release_lock()
        flush_all()


def test_schedule_list_command_shows_defined_tasks(cli_group, runner, console_app_dir) -> None:
    console_route = console_app_dir / "routes" / "console.py"
    console_route.write_text(
        "from aso.console import schedule\nschedule.command('session:prune').daily()\n"
    )
    try:
        result = runner.invoke(cli_group, ["schedule:list"])
        assert result.exit_code == 0
        assert "session:prune" in result.output
        assert "0 0 * * *" in result.output
    finally:
        console_route.unlink()
