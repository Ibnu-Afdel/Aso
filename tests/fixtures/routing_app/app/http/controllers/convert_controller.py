"""Return-value conversion (T-13, T-15): every row of the "What controllers return" table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel
from starlette.responses import PlainTextResponse

from aso.http import Controller

from app.models.post import Post


class Status(StrEnum):
    OPEN = "open"


class Ping(BaseModel):
    ok: bool = True


class ConvertController(Controller):
    async def as_dict(self):
        return {
            "when": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            "amount": Decimal("9.95"),
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "status": Status.OPEN,
        }

    async def as_list(self):
        return [1, 2, 3]

    async def as_none(self):
        return None

    async def as_response(self):
        return PlainTextResponse("plain", status_code=200)

    async def as_model(self):
        post = await Post.create(title="Converted", slug="converted")
        return post

    async def as_pydantic(self):
        return Ping()
