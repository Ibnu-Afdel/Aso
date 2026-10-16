from __future__ import annotations

from aso.http import FormRequest


class ProfileUpdatePayload(FormRequest):
    name: str
