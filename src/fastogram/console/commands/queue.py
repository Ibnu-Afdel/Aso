"""Queue worker and failed-job commands (T-42): `queue:work`, `queue:restart`, `queue:failed`,
`queue:retry`, `queue:forget`, `queue:flush`."""

from __future__ import annotations

from fastogram.console.command import Command
from fastogram.console.registry import register


class QueueWorkCommand(Command):
    signature = "queue:work {--queue= : The queue(s) to listen on} {--concurrency=1 : Number of jobs to process at once}"
    description = "Start processing jobs on the queue as a daemon"

    async def handle(self) -> int:
        from fastogram.queue import drivers, run_worker

        name = drivers.driver_name()
        if drivers.connection_spec(name).get("driver") == "sync":
            self.warn('The "sync" queue connection runs jobs inline at dispatch time; there is no worker to start.')
            return 0
        self.info(f'Processing jobs from the "{name}" connection. (Ctrl+C to stop)')
        queues = self.option("queue")
        try:
            await run_worker(queues=queues, concurrency=int(self.option("concurrency") or 1))
        except KeyboardInterrupt:
            pass
        return 0


class QueueRestartCommand(Command):
    signature = "queue:restart"
    description = "Restart queue worker daemons after their current job"

    async def handle(self) -> int:
        from datetime import UTC, datetime

        from fastogram.cache import cache

        await cache().put("fastogram:queue:restart", datetime.now(UTC).isoformat())
        self.info("Broadcasting queue restart signal.")
        return 0


class QueueFailedCommand(Command):
    signature = "queue:failed"
    description = "List all of the failed queue jobs"

    async def handle(self) -> int:
        from fastogram.queue import list_failed

        rows = await list_failed()
        if not rows:
            self.info("No failed jobs found.")
            return 0
        self.table(
            ["ID", "Connection", "Queue", "Failed At"],
            [[r["id"], r["connection"], r["queue"], r["failed_at"]] for r in rows],
        )
        return 0


class QueueRetryCommand(Command):
    signature = "queue:retry {id?* : The IDs of the jobs to retry} {--all : Retry every failed job}"
    description = "Retry a failed queue job"

    async def handle(self) -> int:
        from fastogram.queue import retry_failed

        if self.option("all"):
            count = await retry_failed("all")
            self.info(f"Retried {count} job(s).")
            return 0
        ids = self.argument("id") or []
        count = 0
        for job_id in ids:
            count += await retry_failed(int(job_id))
        self.info(f"Retried {count} job(s).")
        return 0


class QueueForgetCommand(Command):
    signature = "queue:forget {id : The ID of the failed job}"
    description = "Delete a failed queue job"

    async def handle(self) -> int:
        from fastogram.queue import forget_failed

        ok = await forget_failed(int(self.argument("id")))
        if ok:
            self.info("Failed job deleted successfully.")
            return 0
        self.error("No failed job matches the given ID.")
        return 1


class QueueFlushCommand(Command):
    signature = "queue:flush"
    description = "Flush all of the failed queue jobs"

    async def handle(self) -> int:
        from fastogram.queue import flush_failed

        count = await flush_failed()
        self.info(f"Flushed {count} failed job(s).")
        return 0


def register_all() -> None:
    for cls in (QueueWorkCommand, QueueRestartCommand, QueueFailedCommand, QueueRetryCommand, QueueForgetCommand, QueueFlushCommand):
        register(cls, source="framework")
