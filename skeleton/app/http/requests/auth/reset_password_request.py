"""Validates a password-reset submission (T-38)."""

from typing import Annotated

from pydantic import EmailStr

from aso.http import FormRequest
from aso.validation import Confirmed

from app.actions.auth.password_validation_rules import PasswordValidationRules


class ResetPasswordRequest(FormRequest):
    token: str
    email: EmailStr
    password: Annotated[str, Confirmed(), PasswordValidationRules().rule()]
