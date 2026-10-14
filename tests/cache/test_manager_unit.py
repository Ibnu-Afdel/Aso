"""`cache()` resolution unit tests (T-44): defaults when `config/cache.py` is missing, explicit
config, store selection, `timedelta` TTL."""

from __future__ import annotations

from datetime import timedelta

from fastogram.cache import cache
from fastogram.cache.file import FileDriver
from fastogram.cache.manager import CacheStore, _default_store_name, _driver_for
from fastogram.cache.memory import MemoryDriver
from fastogram.config import set_config


def test_default_store_is_memory_when_environment_is_testing_and_config_is_missing():
    set_config("app.environment", "testing")
    set_config("cache", {})
    assert _default_store_name() == "memory"


def test_default_store_is_file_when_not_testing_and_config_is_missing():
    set_config("app.environment", "production")
    set_config("cache", {})
    try:
        assert _default_store_name() == "file"
    finally:
        set_config("app.environment", "testing")


def test_explicit_default_in_config_wins_over_the_built_in_fallback():
    set_config("cache", {"default": "redis"})
    try:
        assert _default_store_name() == "redis"
    finally:
        set_config("cache", {})


def test_cache_with_no_argument_resolves_the_default_store():
    set_config("app.environment", "testing")
    set_config("cache", {})
    store = cache()
    assert isinstance(store, CacheStore)
    assert isinstance(store._driver, MemoryDriver)  # noqa: SLF001


def test_cache_with_an_explicit_store_name_uses_it_regardless_of_default():
    set_config("cache", {"default": "memory"})
    try:
        store = cache("file")
        assert isinstance(store._driver, FileDriver)  # noqa: SLF001
    finally:
        set_config("cache", {})


def test_unknown_store_name_raises_a_clear_error():
    set_config("cache", {})
    try:
        _driver_for("totally-unknown-store")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "totally-unknown-store" in str(exc)


def test_configured_store_spec_overrides_the_built_in_default_path(tmp_path):
    custom_path = tmp_path / "custom-cache-dir"
    set_config("cache", {"stores": {"file": {"driver": "file", "path": str(custom_path)}}})
    try:
        driver = _driver_for("file")
        assert driver.directory == custom_path
    finally:
        set_config("cache", {})


async def test_put_accepts_a_timedelta_ttl():
    store = CacheStore(MemoryDriver(), "p_")
    await store.put("k", "v", ttl=timedelta(minutes=1))
    assert await store.get("k") == "v"


async def test_prefix_comes_from_cache_config():
    set_config("cache", {"prefix": "custom_prefix_"})
    try:
        store = cache("memory")
        assert store._key("x") == "custom_prefix_x"  # noqa: SLF001
    finally:
        set_config("cache", {})
