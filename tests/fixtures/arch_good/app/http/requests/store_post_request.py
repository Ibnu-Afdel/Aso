from __future__ import annotations

from fastogram.http import FormRequest


class StorePostRequest(FormRequest):
    title: str
