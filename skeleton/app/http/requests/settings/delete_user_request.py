"""Validates account deletion: the current password must be supplied (T-38, settings/profile)."""

from typing import Annotated

from aso.http import FormRequest
from aso.validation import CurrentPassword


class DeleteUserRequest(FormRequest):
    password: Annotated[str, CurrentPassword()]
