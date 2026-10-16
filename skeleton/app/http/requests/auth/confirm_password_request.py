"""Validates a password-confirmation submission (T-38, auth/confirm-password)."""

from aso.http import FormRequest


class ConfirmPasswordRequest(FormRequest):
    password: str
