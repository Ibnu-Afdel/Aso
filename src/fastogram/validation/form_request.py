"""`FormRequest`: Pydantic form requests with Laravel's hooks (T-19).

SEED (spine): input collection (JSON / form), trim + empty→None, required pre-check, Laravel
messages (S-3), `ValidationException`. The validation package task completes T-19 (bracket keys,
files, authorize/prepare_for_validation/after/messages/attributes, async rules in Annotated
metadata, hook-name shadowing check, error_bag/redirect, old input, `validate()`).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from starlette.requests import Request as StarletteRequest

from fastogram.exceptions.types import ValidationException
from fastogram.validation.messages import validate as validate_messages

DONT_TRIM = {"password", "password_confirmation", "current_password"}


def clean_input(value: Any, key: str | None = None) -> Any:
    if isinstance(value, str):
        if key not in DONT_TRIM:
            value = value.strip()
        return value if value != "" else None
    if isinstance(value, dict):
        return {k: clean_input(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_input(v) for v in value]
    return value


async def collect_input(request: StarletteRequest) -> dict[str, Any]:
    data: dict[str, Any] = dict(request.query_params)
    if request.method in ("GET", "HEAD"):
        return data
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        body = await request.json() if await request.body() else {}
        if isinstance(body, dict):
            data.update(body)
    elif "form" in content_type:
        form = await request.form()
        data.update({k: v for k, v in form.multi_items()})
    return data


class FormRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error_bag: ClassVar[str] = "default"
    redirect: ClassVar[str | None] = None

    @classmethod
    async def resolve(cls, request: StarletteRequest) -> FormRequest:
        from fastogram import context

        ctx = context.current()
        if ctx is not None and ctx.request is not None:
            request = ctx.request
        raw = await collect_input(request)
        data = clean_input(raw)
        obj, errors = validate_messages(cls, data)
        if errors:
            raise ValidationException(errors, bag=cls.error_bag, redirect_to=cls.redirect, input=raw)
        assert obj is not None
        return obj  # type: ignore[return-value]

    def validated(self, key: str | None = None) -> Any:
        data = {k: v for k, v in self.model_dump().items() if not k.endswith("_confirmation")}
        return data if key is None else data.get(key)
