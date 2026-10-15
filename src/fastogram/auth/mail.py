"""Built-in mailables the auth library sends itself (T-38): the password-reset link and the
email-verification link. Plain-text content, so they need no app-provided view template."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any
from urllib.parse import quote

from fastogram.mail import Content, Envelope, Mailable

__all__ = ["ResetPasswordMail", "VerifyEmailMail"]


class ResetPasswordMail(Mailable):
    """Sent by `password_broker().send_reset_link()`. `/reset-password/{token}?email=...`."""

    def __init__(self, email: str, token: str) -> None:
        self.email = email
        self.token = token

    def envelope(self) -> Envelope:
        return Envelope(subject="Reset Password Notification")

    def content(self) -> Content:
        return Content(text=f"You are receiving this email because we received a password reset "
                             f"request for your account.\n\nReset your password: {self._url()}\n\n"
                             f"If you did not request a password reset, no further action is required.")

    def _url(self) -> str:
        from fastogram.routing import route, url

        try:
            path = route("password.reset", {"token": self.token})
        except (KeyError, RuntimeError):
            path = f"/reset-password/{self.token}"
        return f"{url(path)}?email={quote(self.email)}"


class VerifyEmailMail(Mailable):
    """Sent by `MustVerifyEmail.send_email_verification_notification()`. A temporary signed URL,
    `/email/verify/{id}/{hash}?expires=...&signature=...` (T-21), valid for 60 minutes."""

    def __init__(self, user: Any) -> None:
        self.user = user

    def envelope(self) -> Envelope:
        return Envelope(subject="Verify Email Address")

    def content(self) -> Content:
        return Content(text=f"Please click the link below to verify your email address.\n\n{self._url()}\n\n"
                             f"If you did not create an account, no further action is required.")

    def _url(self) -> str:
        from fastogram.routing import url

        email_hash = hashlib.sha1(str(self.user.email).lower().encode()).hexdigest()
        return url().temporary_signed_route(
            "verification.verify", timedelta(minutes=60), {"id": self.user.id, "hash": email_hash}
        )
