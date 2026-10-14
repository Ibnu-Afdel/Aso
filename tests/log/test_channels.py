"""Log channel configuration (T-22): `stack`, `single`, `daily`, `stderr`.

`stack`/`single`/`daily` build real `logging.Handler`s that open files under `storage/logs/`.
To keep these tests from writing into whatever `base_path()` happens to be set to by another
package's fixture app (module-global process state, T-03), every test that touches a file-backed
driver monkeypatches `fastogram.log.manager._log_dir` to a pytest `tmp_path`.
"""

from __future__ import annotations

import logging
import logging.handlers

import pytest

from fastogram.log import configure_logging, log
from fastogram.log.manager import _handlers_for


@pytest.fixture(autouse=True)
def _reconfigure_after():
    yield
    configure_logging()


def test_stderr_driver_is_a_stream_handler_to_stderr():
    import sys

    handlers = _handlers_for("stderr", {}, is_prod=False)
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert handlers[0].stream is sys.stderr


def test_single_driver_is_one_file_handler(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    handlers = _handlers_for("single", {}, is_prod=False)
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.FileHandler)
    assert not isinstance(handlers[0], logging.handlers.TimedRotatingFileHandler)


def test_daily_driver_is_a_timed_rotating_file_handler(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    handlers = _handlers_for("daily", {}, is_prod=False)
    assert len(handlers) == 1
    handler = handlers[0]
    assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
    assert handler.when.lower() == "midnight"
    assert handler.backupCount == 14


def test_stack_combines_stderr_and_single_by_default(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    handlers = _handlers_for("stack", {}, is_prod=False)
    kinds = {type(h) for h in handlers}
    assert logging.StreamHandler in kinds
    assert logging.FileHandler in kinds


def test_stack_members_are_configurable(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    handlers = _handlers_for("stack", {"channels": ["daily"]}, is_prod=False)
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.handlers.TimedRotatingFileHandler)


async def test_single_channel_actually_writes_a_line_to_app_log(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    from fastogram.config import set_config

    set_config("logging.channels", {"single": {"driver": "single"}})
    configure_logging()
    log.channel("single").info("hello from single channel", order_id=42)
    for handler in logging.getLogger("fastogram.channel.single").handlers:
        handler.flush()
    content = (tmp_path / "app.log").read_text()
    assert "hello from single channel" in content
    assert "order_id" in content


async def test_daily_channel_writes_to_the_dated_filename_pattern(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    from fastogram.config import set_config

    set_config("logging.channels", {"orders": {"driver": "daily"}})
    configure_logging()
    log.channel("orders").warning("disk usage high")
    for handler in logging.getLogger("fastogram.channel.orders").handlers:
        handler.flush()
    content = (tmp_path / "app.log").read_text()
    assert "disk usage high" in content


def test_unrecognised_driver_defaults_to_a_single_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    handlers = _handlers_for("totally-unknown", {}, is_prod=False)
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.FileHandler)
