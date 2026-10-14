"""Unit tests for the async `Annotated` rules, against a tiny stub `form` (no HTTP/DB needed).

`Unique`/`Exists` (which need `fastogram.database.DB`) and `CurrentPassword` (which needs
`fastogram.auth`/`fastogram.security.hash`) are exercised through the real stack in
`test_integration.py` instead.
"""

from __future__ import annotations

import pytest

from fastogram.validation.rules import (
    Accepted,
    Confirmed,
    CurrentPassword,
    Exists,
    File,
    Image,
    Password,
    Unique,
)
from fastogram.validation.uploaded_file import UploadedFile


class StubForm:
    def __init__(self, input_data: dict | None = None) -> None:
        self._input = input_data or {}

    def input(self, key, default=None):
        return self._input.get(key, default)

    def messages(self) -> dict:
        return {}

    def attributes(self) -> dict:
        return {}

    def user(self):
        return None


async def test_confirmed_passes_and_fails():
    form = StubForm({"password_confirmation": "secret"})
    assert await Confirmed().check("secret", field="password", form=form) is None
    msg = await Confirmed().check("other", field="password", form=form)
    assert msg == "The password field confirmation does not match."


async def test_accepted_rule_true_values_and_false():
    rule = Accepted()
    form = StubForm()
    for value in (True, 1, "1", "yes", "on", "true", "TRUE"):
        assert await rule.check(value, field="terms", form=form) is None
    msg = await rule.check(False, field="terms", form=form)
    assert msg == "The terms field must be accepted."


async def test_file_rule_wrong_mime_and_too_big():
    form = StubForm()
    rule = File(max_kb=1, mimes=["jpg", "png"])
    bad_ext = await rule.check(UploadedFile("photo.gif", "image/gif", b"x"), field="avatar", form=form)
    assert bad_ext == "The avatar field must be a file of type: jpg, png."
    too_big = await rule.check(UploadedFile("photo.jpg", "image/jpeg", b"x" * 2000), field="avatar", form=form)
    assert too_big == "The avatar field must not be greater than 1 kilobytes."
    ok = await rule.check(UploadedFile("photo.jpg", "image/jpeg", b"x"), field="avatar", form=form)
    assert ok is None


async def test_file_rule_rejects_non_uploaded_file():
    msg = await File().check("not-a-file", field="avatar", form=StubForm())
    assert msg == "The avatar field must be a file."


async def test_image_rule_accepts_known_extensions_and_rejects_others():
    form = StubForm()
    rule = Image(max_kb=1)
    assert await rule.check(UploadedFile("a.png", "image/png", b"x"), field="photo", form=form) is None
    msg = await rule.check(UploadedFile("a.txt", "text/plain", b"x"), field="photo", form=form)
    assert msg == "The photo field must be an image."


async def test_password_builder_checks_each_requirement_in_turn():
    form = StubForm()
    rule = Password().min(8).letters().mixed_case().numbers().symbols()
    assert await rule.check("short", field="password", form=form) == (
        "The password field must be at least 8 characters."
    )
    assert await rule.check("alllowercase1!", field="password", form=form) == (
        "The password field must contain at least one uppercase and one lowercase letter."
    )
    assert await rule.check("NoNumbers!Aa", field="password", form=form) == (
        "The password field must contain at least one number."
    )
    assert await rule.check("NoSymbols1Aa", field="password", form=form) == (
        "The password field must contain at least one symbol."
    )
    assert await rule.check("Goo0d!Password1", field="password", form=form) is None


def test_password_defaults_falls_back_without_config():
    rule = Password.defaults()
    assert isinstance(rule, Password)
    assert rule._min == 8 and rule._letters and rule._mixed_case and rule._numbers


def test_unique_and_exists_validate_identifiers_at_construction():
    with pytest.raises(ValueError, match="Invalid table name"):
        Unique("users; drop table users")
    with pytest.raises(ValueError, match="Invalid column name"):
        Exists("teams", "id; drop table teams")


async def test_current_password_without_user_fails_without_touching_security_hash():
    msg = await CurrentPassword().check("x", field="current_password", form=StubForm())
    assert msg == "The current password field is incorrect."
