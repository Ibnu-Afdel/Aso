"""Sends a password-reset link (T-38). The response never reveals whether the email exists."""

from fastogram.auth import password_broker
from fastogram.http import Controller, back
from fastogram.inertia import inertia
from fastogram.session import session
from fastogram.validation import ValidationException

from app.http.requests.auth.forgot_password_request import ForgotPasswordRequest


class PasswordResetLinkController(Controller):
    async def create(self):
        return inertia("auth/forgot-password", {"status": session().get("status")})

    async def store(self, form: ForgotPasswordRequest):
        status = await password_broker().send_reset_link(form.email)
        if status == "throttled":
            raise ValidationException({"email": "Please wait before retrying."})
        return back().with_flash("status", "We have emailed your password reset link.")
