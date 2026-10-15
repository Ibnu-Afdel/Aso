"""Validates account deletion: the current password must be supplied (T-38, settings/profile)."""

from typing import Annotated

from fastogram.http import FormRequest
from fastogram.validation import CurrentPassword


class DeleteUserRequest(FormRequest):
    password: Annotated[str, CurrentPassword()]
