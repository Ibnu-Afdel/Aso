"""`config/queue.py` resolution and defaults when it is missing (T-42)."""

from __future__ import annotations

import pytest

from fastogram.config import set_config
from fastogram.queue import drivers


def test_default_connection_is_sync_without_config():
    assert drivers.driver_name() == "sync"
    assert drivers.connection_spec() == {"driver": "sync"}


def test_redis_default_spec_reads_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6380/2")
    spec = drivers.connection_spec("redis")
    assert spec["driver"] == "redis"
    assert spec["url"] == "redis://example:6380/2"


def test_explicit_config_overrides_the_default():
    set_config("queue.default", "custom")
    set_config("queue.connections", {"custom": {"driver": "sync"}})
    try:
        assert drivers.driver_name() == "custom"
        assert drivers.connection_spec("custom") == {"driver": "sync"}
    finally:
        set_config("queue.default", None)
        set_config("queue.connections", None)


def test_unknown_connection_raises_a_clear_error():
    with pytest.raises(RuntimeError, match="not configured"):
        drivers.connection_spec("nope")


def test_redis_driver_without_taskiq_redis_raises_a_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "taskiq_redis":
            raise ImportError("no taskiq_redis for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(RuntimeError, match="fastogram\\[redis\\]"):
        drivers._redis_broker({"url": "redis://127.0.0.1:6379/0", "queue": "default"})
