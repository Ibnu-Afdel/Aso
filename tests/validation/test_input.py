from __future__ import annotations

from aso.validation.input import clean_input, expand_brackets


def test_clean_input_trims_and_empties_become_none():
    assert clean_input("  hi  ") == "hi"
    assert clean_input("") is None
    assert clean_input("   ") is None


def test_clean_input_does_not_trim_password_keys():
    data = clean_input({"password": "  secret  ", "password_confirmation": "  secret  ",
                         "current_password": "  old  ", "title": "  My Title  "})
    assert data == {"password": "  secret  ", "password_confirmation": "  secret  ",
                     "current_password": "  old  ", "title": "My Title"}


def test_clean_input_recurses_into_dicts_and_lists():
    data = clean_input({"lines": [{"name": "  a  "}, {"name": ""}]})
    assert data == {"lines": [{"name": "a"}, {"name": None}]}


def test_clean_input_leaves_non_strings_alone():
    assert clean_input(5) == 5
    assert clean_input(None) is None
    assert clean_input(True) is True


def test_expand_brackets_simple_nested_object():
    pairs = [("lines[0][quantity]", "2"), ("lines[0][product_id]", "9")]
    assert expand_brackets(pairs) == {"lines": [{"quantity": "2", "product_id": "9"}]}


def test_expand_brackets_multiple_indices():
    pairs = [
        ("lines[0][quantity]", "2"),
        ("lines[1][quantity]", "3"),
    ]
    assert expand_brackets(pairs) == {"lines": [{"quantity": "2"}, {"quantity": "3"}]}


def test_expand_brackets_empty_bracket_appends_in_order():
    pairs = [("tags[]", "a"), ("tags[]", "b"), ("tags[]", "c")]
    assert expand_brackets(pairs) == {"tags": ["a", "b", "c"]}


def test_expand_brackets_plain_keys_pass_through():
    pairs = [("title", "Hello"), ("body", "World")]
    assert expand_brackets(pairs) == {"title": "Hello", "body": "World"}


def test_expand_brackets_mixed_plain_and_nested():
    pairs = [("name", "Order"), ("lines[0][quantity]", "1"), ("note", "")]
    assert expand_brackets(pairs) == {"name": "Order", "lines": [{"quantity": "1"}], "note": ""}
