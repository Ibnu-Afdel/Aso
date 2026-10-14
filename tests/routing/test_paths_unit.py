"""Unit tests for `fastogram.routing.paths` (T-10): parsing, cleaning and compiling route tokens."""

from __future__ import annotations

import pytest

from fastogram.routing import paths


def test_parse_params_extracts_name_binding_field_and_optional():
    specs = paths.parse_params("/posts/{post:slug}/comments/{comment}/{year?}")
    assert [(s.name, s.binding_field, s.optional) for s in specs] == [
        ("post", "slug", False),
        ("comment", None, False),
        ("year", None, True),
    ]


def test_parse_params_rejects_non_trailing_optional():
    with pytest.raises(ValueError):
        paths.parse_params("/archive/{year?}/{month}")


def test_clean_path_strips_binding_field_and_keeps_optional_marker():
    assert paths.clean_path("/posts/{post:slug}") == "/posts/{post}"
    assert paths.clean_path("/archive/{year?}") == "/archive/{year?}"
    assert paths.clean_path("/posts/{post:slug}/{year?}") == "/posts/{post}/{year?}"


def test_clean_path_root():
    assert paths.clean_path("/") == "/"


def test_compiled_variants_single_required_param_has_one_variant():
    variants = paths.compiled_variants("/posts/{post}", lambda name: None)
    assert variants == ["/posts/{post}"]


def test_compiled_variants_optional_param_produces_two_variants_fullest_first():
    variants = paths.compiled_variants("/archive/{year?}", lambda name: None)
    assert variants == ["/archive/{year}", "/archive"]


def test_compiled_variants_uses_type_for_convertor():
    variants = paths.compiled_variants("/orders/{id}", lambda name: "int" if name == "id" else None)
    assert variants == ["/orders/{id:int}"]


def test_compiled_variants_multiple_optional_params_drop_from_the_end():
    variants = paths.compiled_variants("/a/{x?}/{y?}", lambda name: None)
    # NB: parse_params requires optional params to be trailing; both x and y qualify here since
    # this is a flat two-optional-segment path used only to exercise the "drop" loop.
    assert variants[0] == "/a/{x}/{y}"
    assert variants[-1] == "/a"


def test_build_url_substitutes_and_quotes_values():
    url_path, remaining = paths.build_url("/posts/{post}", {"post": 5, "extra": "x"})
    assert url_path == "/posts/5"
    assert remaining == {"extra": "x"}


def test_build_url_drops_missing_optional_segment():
    url_path, remaining = paths.build_url("/archive/{year?}", {})
    assert url_path == "/archive"
    assert remaining == {}


def test_build_url_raises_on_missing_required_param():
    with pytest.raises(KeyError):
        paths.build_url("/posts/{post}", {})


def test_build_url_quotes_special_characters():
    url_path, _ = paths.build_url("/docs/{path}", {"path": "a b/c"})
    assert url_path == "/docs/a%20b%2Fc"


def test_convertor_name_is_stable_and_pattern_specific():
    a = paths.convertor_name(r"[0-9]+")
    b = paths.convertor_name(r"[0-9]+")
    c = paths.convertor_name(r"[a-zA-Z]+")
    assert a == b
    assert a != c
    assert a.startswith("fg_")
