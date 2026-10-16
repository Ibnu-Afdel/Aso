"""Validates a password change from the settings page (T-38, settings/security)."""

from typing import Annotated

from aso.http import FormRequest
from aso.validation import Confirmed, CurrentPassword

from app.actions.auth.password_validation_rules import PasswordValidationRules


class PasswordUpdateRequest(FormRequest):
    current_password: Annotated[str, CurrentPassword()]
    password: Annotated[str, Confirmed(), PasswordValidationRules().rule()]
