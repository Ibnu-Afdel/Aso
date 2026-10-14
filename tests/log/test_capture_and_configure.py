"""`LogCapture` and `configure_logging()` (T-22): capturing records in tests, and that
re-configuring logging is idempotent and never disturbs pytest's own `caplog`."""

from __future__ import annotations

import logging

from fastogram.log import configure_logging, log
from fastogram.log.testing import LogCapture


def test_log_capture_records_message_and_context():
    with LogCapture() as logs:
        log.info("Processing order", order_id=42)
    assert logs.has("Processing order")
    assert logs.records[0]["order_id"] == 42


def test_log_capture_has_is_a_substring_match():
    with LogCapture() as logs:
        log.info("Order #42 created")
    assert logs.has("#42")
    assert not logs.has("nope")


def test_log_capture_only_sees_records_emitted_while_open():
    with LogCapture() as logs:
        pass
    log.info("after close, should not appear")
    assert logs.records == []


def test_log_capture_sees_every_channel():
    with LogCapture() as logs:
        log.channel("one").info("from one")
        log.channel("two").info("from two")
    channels = {r["channel"] for r in logs.records}
    assert channels == {"one", "two"}


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()
    configure_logging()
    with LogCapture() as logs:
        log.info("still works")
    assert logs.has("still works")


def test_configure_logging_does_not_disturb_caplog(caplog):
    configure_logging()
    with caplog.at_level(logging.DEBUG, logger="fastogram"):
        log.info("seen by caplog too")
    assert "seen by caplog too" in caplog.text


def test_reconfiguring_rebuilds_handlers_without_duplicating_them(tmp_path, monkeypatch):
    """Calling `configure_logging()` again after changing config must not pile up old handlers
    on the same channel logger (the manager docstring promises handlers are rebuilt lazily)."""
    monkeypatch.setattr("fastogram.log.manager._log_dir", lambda: tmp_path)
    from fastogram.log.manager import _ensure_channel

    before = len(_ensure_channel("rebuild-test").handlers)
    configure_logging()
    after_first_rebuild = len(_ensure_channel("rebuild-test").handlers)
    configure_logging()
    after_second_rebuild = len(_ensure_channel("rebuild-test").handlers)
    assert after_first_rebuild == before
    assert after_second_rebuild == before
