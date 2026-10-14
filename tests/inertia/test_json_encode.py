"""T-16 "Props: what you can pass" — the JSON conversion rules. Pure unit tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel

from fastogram.inertia.json_encode import to_jsonable


class Color(Enum):
    RED = "red"


class Money(BaseModel):
    amount: Decimal


class WithToDict:
    def to_dict(self) -> dict:
        return {"id": 1, "nested": {"when": datetime(2026, 1, 1, tzinfo=UTC)}}


def test_primitives_pass_through():
    assert to_jsonable(None) is None
    assert to_jsonable("x") == "x"
    assert to_jsonable(True) is True
    assert to_jsonable(42) == 42


def test_datetime_and_date_become_iso_strings():
    dt = datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    assert to_jsonable(dt) == dt.isoformat()
    d = date(2026, 3, 1)
    assert to_jsonable(d) == d.isoformat()


def test_decimal_becomes_a_string():
    assert to_jsonable(Decimal("9.95")) == "9.95"


def test_uuid_becomes_a_string():
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert to_jsonable(u) == str(u)


def test_enum_becomes_its_value():
    assert to_jsonable(Color.RED) == "red"


def test_pydantic_model_uses_model_dump_mode_json():
    money = Money(amount=Decimal("1.50"))
    assert to_jsonable(money) == {"amount": "1.50"}


def test_object_with_to_dict_is_converted_recursively():
    assert to_jsonable(WithToDict()) == {"id": 1, "nested": {"when": "2026-01-01T00:00:00+00:00"}}


def test_dict_and_list_recurse():
    assert to_jsonable({"a": [Decimal("1"), {"b": Color.RED}]}) == {"a": ["1", {"b": "red"}]}
