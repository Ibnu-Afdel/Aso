"""Unit tests for `fastogram.http.encoding.jsonable()` / `to_response()` (T-13, T-15)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from starlette.responses import PlainTextResponse, Response

from fastogram.http.encoding import jsonable, to_response


class Color(Enum):
    RED = "red"


def test_jsonable_decimal_is_a_string():
    assert jsonable(Decimal("9.95")) == "9.95"


def test_jsonable_uuid_is_a_string():
    value = uuid.uuid4()
    assert jsonable(value) == str(value)


def test_jsonable_datetime_is_iso8601():
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert jsonable(dt) == "2026-01-02T03:04:05+00:00"


def test_jsonable_enum_is_its_value():
    assert jsonable(Color.RED) == "red"


def test_jsonable_recurses_into_dicts_and_lists():
    payload = {"amount": Decimal("1.50"), "items": [Decimal("2.00"), Color.RED]}
    assert jsonable(payload) == {"amount": "1.50", "items": ["2.00", "red"]}


def test_jsonable_uses_to_dict_when_available():
    class Thing:
        def to_dict(self):
            return {"a": Decimal("1")}

    assert jsonable(Thing()) == {"a": "1"}


def test_to_response_passes_through_an_existing_response():
    resp = PlainTextResponse("hi")
    assert to_response(resp) is resp


def test_to_response_none_is_204():
    resp = to_response(None)
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_to_response_dict_becomes_json():
    resp = to_response({"a": Decimal("1.5")})
    assert resp.status_code == 200
    assert resp.media_type == "application/json"
