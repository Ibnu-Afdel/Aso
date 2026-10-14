import pytest

from fastogram.session.store import Session, new_id


@pytest.fixture
def s() -> Session:
    return Session(new_id())


# ------------------------------------------------------------ basic get/put


def test_get_put_roundtrip(s: Session) -> None:
    s.put("key", "value")
    assert s.get("key") == "value"
    assert s.get("missing") is None
    assert s.get("missing", "default") == "default"


def test_put_dict_form(s: Session) -> None:
    s.put({"a": 1, "b": 2})
    assert s.get("a") == 1
    assert s.get("b") == 2


def test_dot_notation_get_and_put(s: Session) -> None:
    s.put("user.preferences.theme", "dark")
    assert s.get("user.preferences.theme") == "dark"
    assert s.get("user.preferences") == {"theme": "dark"}
    assert s.all()["user"] == {"preferences": {"theme": "dark"}}


def test_put_non_json_serialisable_raises_immediately(s: Session) -> None:
    class NotJSON:
        pass

    with pytest.raises(TypeError):
        s.put("bad", NotJSON())
    assert s.missing("bad")


def test_push_appends_to_list(s: Session) -> None:
    s.push("user.teams", "developers")
    s.push("user.teams", "admins")
    assert s.get("user.teams") == ["developers", "admins"]


def test_push_onto_non_list_raises(s: Session) -> None:
    s.put("key", "not-a-list")
    with pytest.raises(TypeError):
        s.push("key", "x")


def test_pull_reads_and_deletes(s: Session) -> None:
    s.put("key", "value")
    assert s.pull("key") == "value"
    assert s.missing("key")
    assert s.pull("absent", "fallback") == "fallback"


def test_has_exists_missing(s: Session) -> None:
    s.put("present_none", None)
    s.put("present_value", 1)
    assert s.exists("present_none") is True
    assert s.has("present_none") is False  # has() excludes None
    assert s.exists("present_value") is True
    assert s.has("present_value") is True
    assert s.missing("absent") is True
    assert s.exists("absent") is False


def test_forget_multiple_keys(s: Session) -> None:
    s.put({"a": 1, "b": 2, "c": 3})
    s.forget("a", "c")
    assert s.all().keys() >= set()
    assert s.missing("a")
    assert s.missing("c")
    assert s.get("b") == 2


def test_flush_removes_everything_including_token(s: Session) -> None:
    s.put("a", 1)
    token_before = s.token()
    s.flush()
    assert s.all() == {}
    assert s.missing("a")
    # token() is still safe to call: it lazily regenerates.
    assert s.token() != token_before


def test_only_and_except(s: Session) -> None:
    s.put({"a": 1, "b": 2, "c": 3})
    assert s.only("a", "c") == {"a": 1, "c": 3}
    result = s.except_("a")
    assert "a" not in result
    assert result["b"] == 2 and result["c"] == 3


def test_increment_decrement(s: Session) -> None:
    assert s.increment("views") == 1
    assert s.increment("views", 4) == 5
    assert s.decrement("views") == 4
    assert s.decrement("views", 2) == 2


def test_all_returns_live_data(s: Session) -> None:
    s.put("a", 1)
    assert s.all()["a"] == 1


# ------------------------------------------------------------ dirty tracking


def test_new_session_is_dirty() -> None:
    assert Session(new_id()).dirty is True


def test_loaded_session_is_not_dirty_until_mutated() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    assert s.dirty is False
    s.put("a", 1)
    assert s.dirty is True


# ------------------------------------------------------------ flash ageing (Laravel's Store)


def test_flash_then_age_once_then_gone() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    s.flash("status", "Task was successful!")
    assert s.get("status") == "Task was successful!"

    # outbound of the request that flashed it: still visible.
    s.age_flash()
    assert s.get("status") == "Task was successful!"

    # outbound of the *next* request: gone.
    s.age_flash()
    assert s.missing("status")


def test_now_is_only_visible_for_the_current_request() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    s.now("status", "Done for now")
    assert s.get("status") == "Done for now"
    s.age_flash()  # end of the request that called now()
    assert s.missing("status")


def test_reflash_keeps_everything_one_more_request() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    s.flash("a", 1)
    s.age_flash()  # a moves new -> old
    assert s.get("a") == 1

    s.reflash()
    s.age_flash()  # would have removed "a" without the reflash
    assert s.get("a") == 1

    s.age_flash()
    assert s.missing("a")


def test_keep_preserves_only_the_named_keys() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    s.flash("a", 1)
    s.flash("b", 2)
    s.age_flash()  # a, b move new -> old

    s.keep("a")
    s.age_flash()  # "b" ages out, "a" survives one more request
    assert s.get("a") == 1
    assert s.missing("b")

    s.age_flash()
    assert s.missing("a")


def test_flash_default_value_is_true() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    s.flash("confirmed")
    assert s.get("confirmed") is True


# ------------------------------------------------------------ token / id / regenerate


def test_token_is_present_from_construction() -> None:
    s = Session(new_id())
    assert isinstance(s.token(), str) and s.token()


def test_regenerate_token_changes_token() -> None:
    s = Session(new_id())
    before = s.token()
    s.regenerate_token()
    assert s.token() != before


def test_regenerate_changes_id_and_token_keeps_data() -> None:
    s = Session(new_id(), {"_token": "tok", "cart": [1, 2]}, is_new=False)
    old_id = s.id()
    old_token = s.token()
    s.regenerate()
    assert s.id() != old_id
    assert s.token() != old_token
    assert s.get("cart") == [1, 2]
    assert s.previous_id == old_id
    assert s.destroy_previous is False  # plain regenerate() does not force deletion


def test_regenerate_destroy_true_marks_previous_for_deletion() -> None:
    s = Session(new_id(), {"_token": "tok"}, is_new=False)
    old_id = s.id()
    s.regenerate(destroy=True)
    assert s.previous_id == old_id
    assert s.destroy_previous is True


def test_invalidate_removes_data_and_gets_new_id() -> None:
    s = Session(new_id(), {"_token": "tok", "cart": [1, 2]}, is_new=False)
    old_id = s.id()
    s.invalidate()
    assert s.id() != old_id
    assert s.previous_id == old_id
    assert s.destroy_previous is True
    assert s.get("cart") is None


def test_id_accessor() -> None:
    s = Session("my-id")
    assert s.id() == "my-id"
