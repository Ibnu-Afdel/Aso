"""Laravel `signature` string parsing (D-029, T-50)."""

from __future__ import annotations

import pytest

from fastogram.console.signature import parse_signature


def test_bare_command_name_with_no_tokens() -> None:
    parsed = parse_signature("session:prune")
    assert parsed.name == "session:prune"
    assert parsed.arguments == []
    assert parsed.options == []


@pytest.mark.parametrize(
    ("signature", "expected"),
    [
        ("report:send {user_id}", {"name": "user_id", "optional": False, "is_list": False, "default": None}),
        ("report:send {user_id?}", {"name": "user_id", "optional": True, "is_list": False, "default": None}),
        ("report:send {user_id=1}", {"name": "user_id", "optional": True, "is_list": False, "default": "1"}),
        ("report:send {ids*}", {"name": "ids", "optional": False, "is_list": True, "default": None}),
        ("report:send {ids?*}", {"name": "ids", "optional": True, "is_list": True, "default": None}),
    ],
)
def test_argument_forms(signature: str, expected: dict) -> None:
    parsed = parse_signature(signature)
    arg = parsed.arguments[0]
    assert arg.name == expected["name"]
    assert arg.optional == expected["optional"]
    assert arg.is_list == expected["is_list"]
    assert arg.default == expected["default"]


def test_argument_inline_description() -> None:
    parsed = parse_signature("report:send {user_id : The user to report on}")
    assert parsed.arguments[0].description == "The user to report on"


@pytest.mark.parametrize(
    ("signature", "expected"),
    [
        ("report:send {--queue}", {"name": "queue", "kind": "flag", "default": False, "shortcut": None}),
        ("report:send {--queue=}", {"name": "queue", "kind": "value", "default": None, "shortcut": None}),
        ("report:send {--queue=high}", {"name": "queue", "kind": "value", "default": "high", "shortcut": None}),
        ("report:send {--id=*}", {"name": "id", "kind": "list", "default": [], "shortcut": None}),
        ("report:send {--Q|queue}", {"name": "queue", "kind": "flag", "default": False, "shortcut": "Q"}),
        ("report:send {--Q|queue=high}", {"name": "queue", "kind": "value", "default": "high", "shortcut": "Q"}),
    ],
)
def test_option_forms(signature: str, expected: dict) -> None:
    parsed = parse_signature(signature)
    opt = parsed.options[0]
    assert opt.name == expected["name"]
    assert opt.kind == expected["kind"]
    assert opt.default == expected["default"]
    assert opt.shortcut == expected["shortcut"]


def test_option_inline_description() -> None:
    parsed = parse_signature("report:send {--queue : Dispatch as a background job}")
    assert parsed.options[0].description == "Dispatch as a background job"


def test_mixed_arguments_and_options_in_declared_order() -> None:
    parsed = parse_signature("user:create-admin {name} {email?} {--Q|queue} {--level=info}")
    assert [a.name for a in parsed.arguments] == ["name", "email"]
    assert [o.name for o in parsed.options] == ["queue", "level"]


def test_signature_name_may_have_no_leading_space_before_brace() -> None:
    parsed = parse_signature("report:send{user_id}")
    assert parsed.name == "report:send"
    assert parsed.arguments[0].name == "user_id"


def test_parsed_signature_lookup_helpers() -> None:
    parsed = parse_signature("report:send {user_id} {--queue}")
    assert parsed.argument("user_id") is not None
    assert parsed.argument("missing") is None
    assert parsed.option("queue") is not None
    assert parsed.option("missing") is None
