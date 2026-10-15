"""Resends the email-verification link (T-38). Throttled 6/min by the `email/verification-notification` route."""

from fastogram.auth import auth
from fastogram.http import Controller, redirect
from fastogram.routing import route


class EmailVerificationNotificationController(Controller):
    async def store(self):
        user = auth().user()
        if user is not None and user.has_verified_email():
            return redirect().to(route("dashboard"))
        if user is not None:
            await user.send_email_verification_notification()
        return redirect().back().with_flash("status", "verification-link-sent")
