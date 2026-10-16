from __future__ import annotations

from aso.http import FormRequest


class StorePostRequest(FormRequest):
    title: str
