"""`SendQueuedMail`: the built-in job `Mail.to(...).queue(mailable)` dispatches (T-41, D-028).

The message was already fully rendered (subject, HTML, text, attachments as base64) before this
job was built, so its only argument is that plain-JSON dict -- no model serialisation exists
anywhere in the mail-queueing path.
"""

from __future__ import annotations

from typing import Any

from aso.queue.job import Job


class SendQueuedMail(Job):
    after_commit = True  # D-028: queued mail follows the job rules, after_commit by default

    def __init__(self, message: dict[str, Any]) -> None:
        self.message = message

    async def handle(self) -> None:
        from aso.mail.drivers import deliver_message

        await deliver_message(self.message)
