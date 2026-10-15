from __future__ import annotations

from fastogram.http import FormRequest


class ProfileUpdatePayload(FormRequest):
    name: str
