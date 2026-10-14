from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

import pytest
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from messages import validate


class Line(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)


class Color(enum.Enum):
    red = "red"


class Form(BaseModel):
    model_config = {"extra": "ignore"}
    title: str = Field(default="ok", min_length=3, max_length=10)
    age: int = 1
    price: float = 1.0
    amount: Decimal = Decimal(1)
    newsletter: bool = False
    email: EmailStr = "a@b.co"
    website: HttpUrl = "https://x.io"
    published_at: datetime = datetime(2020, 1, 1)
    born: date = date(2020, 1, 1)
    slug: str = Field(default="ok", pattern=r"^[a-z-]+$")
    theme: Literal["light", "dark"] = "light"
    color: Color = Color.red
    id: UUID = UUID(int=1)
    lines: list[Line] = Field(default_factory=lambda: [Line(product_id=1, quantity=1)], min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=2)
    qty: int = Field(default=5, multiple_of=5)
    total: int = Field(default=1, gt=0)
    nick: str = "x"

    @field_validator("nick")
    @classmethod
    def no_admin(cls, v: str) -> str:
        if v == "admin":
            raise ValueError("The nick may not be admin.")
        return v


class Required(BaseModel):
    title: str
    body: str | None = None


CASES = [
    ({"title": "ab"}, "title", "The title field must be at least 3 characters."),
    ({"title": "x" * 11}, "title", "The title field must not be greater than 10 characters."),
    ({"age": "abc"}, "age", "The age field must be an integer."),
    ({"age": 1.5}, "age", "The age field must be an integer."),
    ({"price": "abc"}, "price", "The price field must be a number."),
    ({"amount": "abc"}, "amount", "The amount field must be a number."),
    ({"newsletter": "maybe"}, "newsletter", "The newsletter field must be true or false."),
    ({"email": "nope"}, "email", "The email field must be a valid email address."),
    ({"website": "nope"}, "website", "The website field must be a valid URL."),
    ({"published_at": "nope"}, "published_at", "The published at field must be a valid date."),
    ({"born": "nope"}, "born", "The born field must be a valid date."),
    ({"slug": "Bad Slug"}, "slug", "The slug field format is invalid."),
    ({"theme": "blue"}, "theme", "The selected theme is invalid."),
    ({"color": "blue"}, "color", "The selected color is invalid."),
    ({"id": "nope"}, "id", "The id field must be a valid UUID."),
    ({"lines": []}, "lines", "The lines field must have at least 1 items."),
    ({"tags": ["a", "b", "c"]}, "tags", "The tags field must not have more than 2 items."),
    ({"lines": [{"product_id": 1, "quantity": 0}]}, "lines.0.quantity", "The quantity field must be at least 1."),
    ({"lines": [{"product_id": 1, "quantity": 100}]}, "lines.0.quantity", "The quantity field must not be greater than 99."),
    ({"qty": 7}, "qty", "The qty field must be a multiple of 5."),
    ({"total": 0}, "total", "The total field must be greater than 0."),
    ({"nick": "admin"}, "nick", "The nick may not be admin."),
    ({"tags": "x"}, "tags", "The tags field must be an array."),
    ({"title": 5}, "title", "The title field must be a string."),
]


@pytest.mark.parametrize("data,key,message", CASES)
def test_message(data, key, message):
    obj, errors = validate(Form, data)
    assert obj is None
    assert errors[key][0] == message, errors


def test_required_missing_and_empty_string_become_none():
    _, errors = validate(Required, {})
    assert errors == {"title": ["The title field is required."]}
    _, errors = validate(Required, {"title": None})   # "" is converted to None before (step 2)
    assert errors == {"title": ["The title field is required."]}


def test_custom_messages_and_attributes():
    _, errors = validate(Form, {"title": "ab"}, custom={"title.min": "Titles need :min chars."})
    assert errors["title"] == ["Titles need 3 chars."]
    _, errors = validate(Form, {"published_at": "x"}, attributes={"published_at": "publish date"})
    assert errors["published_at"] == ["The publish date field must be a valid date."]


async def test_async_after_hook():
    class Invoice(BaseModel):
        issued_on: date
        due_on: date

        async def after(self, add_error):
            if self.due_on < self.issued_on:
                add_error("due_on", "The due date must be after the issue date.")

    obj, errors = validate(Invoice, {"issued_on": "2026-01-02", "due_on": "2026-01-01"})
    assert not errors
    after_errors: dict[str, list[str]] = {}
    await obj.after(lambda k, m: after_errors.setdefault(k, []).append(m))
    assert after_errors == {"due_on": ["The due date must be after the issue date."]}
