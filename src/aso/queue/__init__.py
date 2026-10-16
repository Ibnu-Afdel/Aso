"""Queues and jobs (T-42, D-011): `Job`, `await SendWelcomeEmail(...).dispatch()`.

```python
from aso.queue import Job, Queue

class SendWelcomeEmail(Job):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    async def handle(self) -> None: ...

await SendWelcomeEmail(user_id=1).dispatch()
```

Drivers `sync` (default in dev/testing, runs inline reusing the caller's database scope) and
`redis` (taskiq + taskiq-redis, optional extra `aso[redis]`). `Queue.fake()` plus
class-level assertions for tests. `config/queue.py` defaults when missing (`drivers.py`).
"""

from __future__ import annotations

from aso.exceptions.types import JobNotSerializable
from aso.queue.failed import flush_failed, forget_failed, list_failed, retry_failed
from aso.queue.job import Job
from aso.queue.manager import Queue, reset_queue, run_job
from aso.queue.worker import run_worker

__all__ = [
    "Job",
    "JobNotSerializable",
    "Queue",
    "flush_failed",
    "forget_failed",
    "list_failed",
    "reset_queue",
    "retry_failed",
    "run_job",
    "run_worker",
]
