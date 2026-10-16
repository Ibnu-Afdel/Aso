"""The skeleton's one built-in auth listener (T-38): `Registered` -> send the verification mail
when the user model uses `MustVerifyEmail`. Records to a module-level list so the test can see it
ran inline (`tests/conftest.py` purges this module between tests)."""

from __future__ import annotations

from aso.auth.events import Registered

calls: list[int] = []


class SendEmailVerificationNotification:
    async def handle(self, event: Registered) -> None:
        calls.append(event.user.id)
        send = getattr(event.user, "send_email_verification_notification", None)
        if callable(send):
            await send()
