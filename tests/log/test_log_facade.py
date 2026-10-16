"""`log` / `log.channel()` (T-22): the five core levels plus Laravel's RFC 5424 extras."""

from __future__ import annotations

from aso.log import configure_logging, log
from aso.log.manager import ChannelLogger
from aso.log.testing import LogCapture


def test_log_channel_returns_a_channel_logger():
    channel = log.channel("orders")
    assert isinstance(channel, ChannelLogger)
    assert channel.channel == "orders"


def test_core_levels_all_emit_a_record():
    from aso.config import set_config

    # Explicit, not relying on whatever "app.environment" another test/process state left behind
    # (the default channel level is "info" unless the app is non-production, T-22).
    set_config("logging.level", "debug")
    configure_logging()
    try:
        with LogCapture() as logs:
            log.debug("d")
            log.info("i")
            log.warning("w")
            log.error("e")
            log.critical("c")
    finally:
        set_config("logging.level", None)
        configure_logging()
    levels = [r["level"] for r in logs.records]
    assert levels == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_notice_maps_to_info():
    with LogCapture() as logs:
        log.notice("n")
    assert logs.records[0]["level"] == "INFO"


def test_alert_and_emergency_map_to_critical():
    with LogCapture() as logs:
        log.alert("a")
        log.emergency("e")
    assert [r["level"] for r in logs.records] == ["CRITICAL", "CRITICAL"]


def test_log_channel_x_info_tags_the_record_with_its_channel_name():
    with LogCapture() as logs:
        log.channel("orders").warning("disk usage high", usage_percent=88)
    record = logs.records[0]
    assert record["channel"] == "orders"
    assert record["usage_percent"] == 88


def test_different_channels_are_independent_loggers():
    from aso.log.manager import _ensure_channel

    a = _ensure_channel("alpha")
    b = _ensure_channel("beta")
    assert a is not b
    assert a.name == "aso.channel.alpha"
    assert b.name == "aso.channel.beta"
