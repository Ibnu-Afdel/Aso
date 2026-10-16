"""Validates a new registration (T-38)."""

from typing import Annotated

from pydantic import EmailStr, Field

from aso.http import FormRequest
from aso.validation import Confirmed, Unique

from app.actions.auth.password_validation_rules import PasswordValidationRules


class RegisterRequest(FormRequest):
    name: str = Field(max_length=255)
    email: Annotated[EmailStr, Unique("users")]
    password: Annotated[str, Confirmed(), PasswordValidationRules().rule()]
