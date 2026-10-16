import pytest

from aso.security import hash


@pytest.fixture(autouse=True)
def _reset_hasher_cache():
    hash._reset_cache()
    yield
    hash._reset_cache()


def test_make_and_check_roundtrip() -> None:
    hashed = hash.make("secret-value")
    assert hashed != "secret-value"
    assert hash.check("secret-value", hashed) is True
    assert hash.check("wrong-value", hashed) is False


def test_make_is_salted_and_non_deterministic() -> None:
    assert hash.make("secret-value") != hash.make("secret-value")


def test_check_never_raises_on_malformed_hash() -> None:
    assert hash.check("secret-value", "not-a-real-hash") is False
    assert hash.check("secret-value", "") is False


def test_needs_rehash_false_for_current_settings() -> None:
    hashed = hash.make("secret-value")
    assert hash.needs_rehash(hashed) is False


def test_needs_rehash_true_after_cost_change(monkeypatch) -> None:
    hashed = hash.make("secret-value")
    monkeypatch.setattr("aso.config.config", lambda *a, **kw: {"memory_cost": 8, "time_cost": 1, "parallelism": 1})
    hash._reset_cache()
    assert hash.needs_rehash(hashed) is True
