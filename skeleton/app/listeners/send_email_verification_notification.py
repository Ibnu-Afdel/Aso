"""`Registered` -> send the verification mail, when the user model uses `MustVerifyEmail` (T-38,
T-46). Registered in `bootstrap/app.py`. Not `queued = True`: `send_email_verification_notification()`
calls `Mail.to(user).send(VerifyEmailMail(user))` directly (and auth events carry the `User`
model, so their listeners can never be queued anyway, T-46).
"""

from fastogram.auth import MustVerifyEmail
from fastogram.auth.events import Registered


class SendEmailVerificationNotification:
    async def handle(self, event: Registered) -> None:
        if isinstance(event.user, MustVerifyEmail) and not event.user.has_verified_email():
            await event.user.send_email_verification_notification()
