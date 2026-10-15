"""`session:prune`, `storage:link`, `queue:*` (T-18, T-43, T-42)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner


def test_session_prune_runs_without_a_configured_sessions_table(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["session:prune"])
    assert result.exit_code == 0
    assert "Pruned" in result.output


def test_storage_link_creates_a_relative_symlink(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    link = console_app_dir / "public" / "storage"
    try:
        result = runner.invoke(cli_group, ["storage:link"])
        assert result.exit_code == 0, result.output
        assert link.is_symlink()
    finally:
        if link.exists() or link.is_symlink():
            link.unlink()
        public_dir = console_app_dir / "public"
        if public_dir.exists() and not any(public_dir.iterdir()):
            public_dir.rmdir()
        storage_app = console_app_dir / "storage" / "app"
        if storage_app.exists():
            import shutil

            shutil.rmtree(storage_app)


def test_queue_work_on_sync_connection_explains_there_is_nothing_to_run(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["queue:work"])
    assert result.exit_code == 0
    assert "sync" in result.output.lower()


def test_queue_failed_lifecycle(cli_group, runner: CliRunner) -> None:
    empty = runner.invoke(cli_group, ["queue:failed"])
    assert empty.exit_code == 0
    assert "No failed jobs" in empty.output

    import asyncio

    from fastogram.queue.failed import record_failed_job

    async def _seed() -> None:
        from fastogram.database.scope import open_scope

        async with open_scope():
            await record_failed_job({"uuid": "abc", "connection": "sync", "queue": "default"}, RuntimeError("boom"))

    asyncio.run(_seed())

    listed = runner.invoke(cli_group, ["queue:failed"])
    assert listed.exit_code == 0
    assert "abc" not in listed.output  # uuid isn't a column we print, but the row should be there
    assert "sync" in listed.output

    flushed = runner.invoke(cli_group, ["queue:flush"])
    assert flushed.exit_code == 0
    assert "Flushed 1" in flushed.output

    empty_again = runner.invoke(cli_group, ["queue:failed"])
    assert "No failed jobs" in empty_again.output


def test_queue_restart_sets_a_cache_signal(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["queue:restart"])
    assert result.exit_code == 0
    assert "restart" in result.output.lower()


def test_queue_restart_signal_is_newer_than_a_worker_started_before_it(cli_group, runner: CliRunner) -> None:
    import asyncio
    from datetime import UTC, datetime

    from fastogram.queue.worker import _restart_requested

    started_at = datetime.now(UTC)
    result = runner.invoke(cli_group, ["queue:restart"])
    assert result.exit_code == 0
    assert asyncio.run(_restart_requested(started_at)) is True


def test_db_wipe_drops_every_table(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    runner.invoke(cli_group, ["migrate"])
    before = runner.invoke(cli_group, ["db:show"])
    assert "posts" in before.output

    result = runner.invoke(cli_group, ["db:wipe"])
    assert result.exit_code == 0

    after = runner.invoke(cli_group, ["db:show"])
    assert "posts" not in after.output
