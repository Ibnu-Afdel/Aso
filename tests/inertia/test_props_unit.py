"""`fastogram.inertia.props` — the modifier chaining rules (T-16). Pure unit tests."""

from __future__ import annotations

from datetime import timedelta

from fastogram.inertia.props import Prop, always, deep_merge, defer, merge, once, optional, scroll


def test_optional_sets_only_the_optional_flag():
    p = optional(lambda: 1)
    assert isinstance(p, Prop)
    assert p.optional_flag is True
    assert p.always_flag is False


def test_always_sets_only_the_always_flag():
    p = always(lambda: 1)
    assert p.always_flag is True


def test_defer_defaults_to_the_default_group_and_no_rescue():
    p = defer(lambda: 1)
    assert p.defer_group == "default"
    assert p.rescue is False


def test_defer_accepts_group_and_rescue():
    p = defer(lambda: 1, group="attributes", rescue=True)
    assert p.defer_group == "attributes"
    assert p.rescue is True


def test_merge_sets_merge_flag_only():
    p = merge(lambda: 1)
    assert p.merge_flag is True
    assert p.deep_merge_flag is False


def test_deep_merge_sets_both_merge_and_deep_merge_flags():
    p = deep_merge(lambda: 1)
    assert p.merge_flag is True
    assert p.deep_merge_flag is True


def test_append_sets_merge_flag_and_combined_match_on_path():
    p = merge(lambda: 1).append("data", match_on="id")
    assert p.merge_flag is True
    assert p.match_on_path == "data.id"


def test_append_without_a_sub_path_uses_match_on_alone():
    p = merge(lambda: 1).append(match_on="id")
    assert p.match_on_path == "id"


def test_match_on_sets_an_arbitrary_relative_path():
    p = deep_merge(lambda: 1).match_on("messages.id")
    assert p.match_on_path == "messages.id"


def test_prepend_sets_merge_and_prepend_flags():
    p = merge(lambda: 1).prepend()
    assert p.merge_flag is True
    assert p.prepend_flag is True


def test_once_sets_the_once_flag():
    p = once(lambda: 1)
    assert p.once_flag is True


def test_once_until_stores_the_duration_or_datetime():
    p = once(lambda: 1).until(timedelta(days=1))
    assert p.once_until == timedelta(days=1)


def test_once_as_sets_a_shared_cache_identity():
    p = once(lambda: 1).as_("roles")
    assert p.once_as == "roles"


def test_once_fresh_forces_a_bool():
    p = once(lambda: 1).fresh(1)
    assert p.once_fresh is True


def test_scroll_sets_scroll_and_merge_flags():
    p = scroll(lambda: 1)
    assert p.scroll_flag is True
    assert p.merge_flag is True


def test_modifiers_combine_defer_then_once():
    p = defer(lambda: 1).once()
    assert p.defer_group == "default"
    assert p.once_flag is True


def test_modifiers_combine_optional_then_once():
    p = optional(lambda: 1).once()
    assert p.optional_flag is True
    assert p.once_flag is True
