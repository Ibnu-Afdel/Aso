"""Validates a profile update (T-38, settings/profile)."""

from typing import Annotated

from pydantic import EmailStr, Field

from aso.http import FormRequest
from aso.validation import Unique


class ProfileUpdateRequest(FormRequest):
    name: str = Field(max_length=255)
    email: Annotated[EmailStr, Unique("users", ignore=lambda form: form.user().id)]
