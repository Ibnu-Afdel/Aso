"""Validates a "forgot password" request (T-38)."""

from pydantic import EmailStr

from aso.http import FormRequest


class ForgotPasswordRequest(FormRequest):
    email: EmailStr
