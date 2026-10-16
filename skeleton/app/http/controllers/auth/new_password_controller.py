"""Shows the reset-password form and sets the new password (T-38)."""

from aso.auth import password_broker
from aso.http import Controller, Request, redirect
from aso.inertia import inertia
from aso.validation import ValidationException

from app.actions.auth.password_validation_rules import PasswordValidationRules
from app.http.requests.auth.reset_password_request import ResetPasswordRequest


class NewPasswordController(Controller):
    async def create(self, request: Request, token: str):
        return inertia(
            "auth/reset-password",
            {
                "token": token,
                "email": request.query("email", ""),
                "passwordRules": PasswordValidationRules().description(),
            },
        )

    async def store(self, form: ResetPasswordRequest):
        ok = await password_broker().reset(form.email, form.token, form.password)
        if not ok:
            raise ValidationException({"email": "This password reset token is invalid."})
        return redirect().route("login").with_flash("status", "Your password has been reset.")
