"""T-56: `AssertableInertia` against hand-built page dicts -- unit-level coverage for the parts
of the page-assertion API that the `testing_app` fixture doesn't happen to exercise (`.each()`,
`.encrypts_history()`, `missing_flash()`, `where_type()`'s boolean/integer distinction).
"""

from __future__ import annotations

import pytest

from fastogram.testing.inertia_assert import AssertableInertia


def _page(**props: object) -> dict[str, object]:
    return {"component": "x", "url": "/x", "version": "1", "props": props}


def test_each_runs_the_callback_against_every_item() -> None:
    page = _page(comments=[{"id": 1, "body": "a"}, {"id": 2, "body": "b"}])
    AssertableInertia(page).each("comments", lambda c: c.has("id").has("body").etc())


def test_each_is_strict_per_item() -> None:
    page = _page(comments=[{"id": 1, "body": "a", "secret": "nope"}])
    with pytest.raises(AssertionError):
        AssertableInertia(page).each("comments", lambda c: c.has("id").has("body"))


def test_encrypts_history_true_and_false() -> None:
    encrypted = _page()
    encrypted["encryptHistory"] = True
    AssertableInertia(encrypted).encrypts_history()

    plain = _page()
    with pytest.raises(AssertionError):
        AssertableInertia(plain).encrypts_history()


def test_missing_flash() -> None:
    page = _page()
    page["flash"] = {"success": "ok"}
    AssertableInertia(page).missing_flash("error")
    with pytest.raises(AssertionError):
        AssertableInertia(page).missing_flash("success")


def test_where_type_distinguishes_boolean_from_integer() -> None:
    page = _page(active=True, count=3)
    AssertableInertia(page).where_type("active", "boolean").where_type("count", "integer")
    with pytest.raises(AssertionError):
        AssertableInertia(page).where_type("active", "integer")
    with pytest.raises(AssertionError):
        AssertableInertia(page).where_type("count", "boolean")


def test_where_type_null_and_union() -> None:
    page = _page(middle_name=None)
    AssertableInertia(page).where_type("middle_name", "null")
    AssertableInertia(page).where_type("middle_name", "string|null")


def test_has_deferred_with_a_named_group() -> None:
    page = _page()
    page["deferredProps"] = {"sidebar": ["teams", "projects"]}
    AssertableInertia(page).has_deferred("teams", group="sidebar")
    with pytest.raises(AssertionError):
        AssertableInertia(page).has_deferred("teams", group="default")


def test_component_mismatch_message_shows_both_names() -> None:
    page = _page()
    with pytest.raises(AssertionError) as excinfo:
        AssertableInertia(page).component("posts/show")
    message = str(excinfo.value)
    assert "posts/show" in message
    assert "x" in message
