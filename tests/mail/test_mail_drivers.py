"""Mail transports: `array`, `log`, `smtp` (T-41). SMTP is mocked (`aiosmtplib.send`); no
network traffic happens in this suite."""

from __future__ import annotations

import pytest

from aso.mail.drivers import (
    _deliver_log,
    _deliver_smtp,
    array_messages,
    deliver_message,
    mailer_spec,
    reset_array,
)

_MESSAGE = {
    "to": ["a@example.com"],
    "cc": ["c@example.com"],
    "bcc": [],
    "from": {"address": "hello@example.com", "name": "Aso"},
    "reply_to": [],
    "subject": "Hi",
    "html": "<p>Hi</p>",
    "text": "Hi",
    "attachments": [],
}


# ------------------------------------------------------------ array


async def test_array_driver_records_messages():
    await deliver_message(_MESSAGE, mailer="array")
    assert array_messages() == [_MESSAGE]


async def test_reset_array_clears_recorded_messages():
    await deliver_message(_MESSAGE, mailer="array")
    reset_array()
    assert array_messages() == []


# ------------------------------------------------------------ log


async def test_log_driver_writes_the_message_via_log_info(monkeypatch):
    from aso.log import log as real_log

    captured = {}

    def fake_info(message, **context):
        captured["message"] = message
        captured["context"] = context

    monkeypatch.setattr(real_log, "info", fake_info)

    await deliver_message(_MESSAGE, mailer="log")

    assert captured["message"] == "Mail"
    assert captured["context"]["subject"] == "Hi"
    assert captured["context"]["to"] == ["a@example.com"]
    assert captured["context"]["cc"] == ["c@example.com"]


def test_log_driver_with_no_channel_logs_through_the_default_channel(monkeypatch):
    from aso.log import log as real_log

    captured = {}
    monkeypatch.setattr(real_log, "info", lambda message, **ctx: captured.update(message=message))

    _deliver_log(_MESSAGE, {"channel": None})

    assert captured == {"message": "Mail"}


def test_log_driver_with_a_channel_logs_through_log_channel(monkeypatch):
    """`"channel": None` (the default) logs through the default channel; a named one goes
    through `log.channel(name)` instead (T-41: `MAIL_LOG_CHANNEL`)."""
    from aso.log import log as real_log

    seen = {}

    class FakeChannelLogger:
        def info(self, message, **context):
            seen["message"] = message

    def fake_channel(name):
        seen["name"] = name
        return FakeChannelLogger()

    monkeypatch.setattr(real_log, "channel", fake_channel)

    _deliver_log(_MESSAGE, {"channel": "orders"})

    assert seen == {"name": "orders", "message": "Mail"}


# ------------------------------------------------------------ smtp


async def test_smtp_driver_builds_the_email_message_and_calls_aiosmtplib_send(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr("aiosmtplib.send", fake_send)

    message = {
        **_MESSAGE,
        "attachments": [{"name": "a.txt", "content_type": "text/plain", "data_b64": "aGVsbG8="}],
    }
    await deliver_message(message, mailer="smtp")

    email_message = captured["message"]
    assert email_message["From"] == "Aso <hello@example.com>"
    assert email_message["To"] == "a@example.com"
    assert email_message["Cc"] == "c@example.com"
    assert email_message["Subject"] == "Hi"
    assert email_message.get_content_type() == "multipart/mixed"
    assert captured["kwargs"]["hostname"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 2525


async def test_smtp_scheme_none_uses_starttls_negotiation_not_forced(monkeypatch):
    """"None/`"smtp"`: STARTTLS when offered" (T-41 `config/mail.py`): `start_tls=None` lets
    aiosmtplib negotiate, instead of forcing an upgrade a server might not advertise."""
    captured = {}

    async def fake_send(message, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr("aiosmtplib.send", fake_send)

    await _deliver_smtp(_MESSAGE, {"host": "smtp.example.com", "port": 587, "scheme": None})

    assert captured["kwargs"]["use_tls"] is False
    assert captured["kwargs"]["start_tls"] is None


async def test_smtp_scheme_smtps_connects_over_tls_from_the_start(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr("aiosmtplib.send", fake_send)

    await _deliver_smtp(_MESSAGE, {"host": "smtp.example.com", "port": 465, "scheme": "smtps"})

    assert captured["kwargs"]["use_tls"] is True
    assert captured["kwargs"]["start_tls"] is None


async def test_smtp_driver_passes_credentials_through(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr("aiosmtplib.send", fake_send)

    await _deliver_smtp(
        _MESSAGE, {"host": "h", "port": 587, "username": "user", "password": "pw", "scheme": None}
    )

    assert captured["kwargs"]["username"] == "user"
    assert captured["kwargs"]["password"] == "pw"


# ------------------------------------------------------------ errors


async def test_unknown_transport_raises(monkeypatch):
    """A mailer *is* configured, but its `transport` names none of `array`/`log`/`smtp`."""
    monkeypatch.setattr("aso.mail.drivers.mailer_spec", lambda name=None: {"transport": "carrier-pigeon"})

    with pytest.raises(RuntimeError, match="transport"):
        await deliver_message(_MESSAGE, mailer="exotic")


def test_mailer_spec_for_an_unknown_name_raises():
    with pytest.raises(RuntimeError, match="not configured"):
        mailer_spec("totally-unknown")


def test_mailer_spec_falls_back_to_the_built_in_defaults_for_array_log_smtp():
    assert mailer_spec("array") == {"transport": "array"}
    assert mailer_spec("log")["transport"] == "log"
    assert mailer_spec("smtp")["transport"] == "smtp"
