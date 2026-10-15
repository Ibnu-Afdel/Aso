"""Mail transports: `log` (default locally), `array` (tests), `smtp` (`aiosmtplib`) (T-41).

All three take the same wire-shaped `dict` (`to`, `cc`, `bcc`, `from`, `reply_to`, `subject`,
`html`, `text`, `attachments: [{name, content_type, data_b64}]`) so the same function delivers a
message built just now (`Mail.to().send()`) or rebuilt in a worker (`SendQueuedMail`, D-028).
"""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

_array_log: list[dict[str, Any]] = []


def default_mailer_name() -> str:
    from fastogram.config import config, env

    return config("mail.default") or env("MAIL_MAILER", "log")


def mailer_spec(name: str | None = None) -> dict[str, Any]:
    from fastogram.config import config, env

    name = name or default_mailer_name()
    mailers = config("mail.mailers")
    if isinstance(mailers, dict) and name in mailers:
        return mailers[name]
    defaults: dict[str, dict[str, Any]] = {
        "log": {"transport": "log", "channel": None},
        "array": {"transport": "array"},
        "smtp": {
            "transport": "smtp",
            "host": env("MAIL_HOST", "127.0.0.1"),
            "port": int(env("MAIL_PORT", 2525)),
            "username": env("MAIL_USERNAME", None),
            "password": env("MAIL_PASSWORD", None),
            "scheme": env("MAIL_SCHEME", None),
        },
    }
    if name in defaults:
        return defaults[name]
    raise RuntimeError(f'Mailer "{name}" is not configured. Add it to config/mail.py `mailers`.')


def default_from_address() -> dict[str, str]:
    from fastogram.config import config, env

    configured = config("mail.from_address")
    if isinstance(configured, dict):
        return configured
    return {"address": env("MAIL_FROM_ADDRESS", "hello@example.com"), "name": env("MAIL_FROM_NAME", "FastoGram")}


async def deliver_message(message: dict[str, Any], mailer: str | None = None) -> None:
    spec = mailer_spec(mailer)
    transport = spec.get("transport", mailer or default_mailer_name())
    if transport == "array":
        _array_log.append(message)
        return
    if transport == "log":
        _deliver_log(message, spec)
        return
    if transport == "smtp":
        await _deliver_smtp(message, spec)
        return
    raise RuntimeError(f'Unknown mail transport "{transport}".')


def _deliver_log(message: dict[str, Any], spec: dict[str, Any]) -> None:
    from fastogram.log import log

    channel = spec.get("channel")
    logger = log.channel(channel) if channel else log
    logger.info(
        "Mail",
        subject=message.get("subject"),
        to=message.get("to"),
        cc=message.get("cc"),
        bcc=message.get("bcc"),
        html=message.get("html"),
        text=message.get("text"),
    )


async def _deliver_smtp(message: dict[str, Any], spec: dict[str, Any]) -> None:
    import aiosmtplib

    email_message = _build_email_message(message)
    scheme = spec.get("scheme")
    use_tls = scheme == "smtps"
    await aiosmtplib.send(
        email_message,
        hostname=spec.get("host", "127.0.0.1"),
        port=int(spec.get("port", 2525)),
        username=spec.get("username") or None,
        password=spec.get("password") or None,
        use_tls=use_tls,
        start_tls=None if use_tls else True,
    )


def _build_email_message(message: dict[str, Any]) -> EmailMessage:
    email_message = EmailMessage()
    from_ = message.get("from") or {}
    email_message["From"] = _format_address(from_.get("address"), from_.get("name"))
    email_message["To"] = ", ".join(message.get("to") or [])
    if message.get("cc"):
        email_message["Cc"] = ", ".join(message["cc"])
    if message.get("reply_to"):
        reply_to = message["reply_to"]
        email_message["Reply-To"] = ", ".join(reply_to) if isinstance(reply_to, list) else reply_to
    email_message["Subject"] = message.get("subject", "")
    email_message.set_content(message.get("text") or "")
    if message.get("html"):
        email_message.add_alternative(message["html"], subtype="html")
    for attachment in message.get("attachments") or []:
        data = base64.b64decode(attachment["data_b64"])
        maintype, _, subtype = (attachment.get("content_type") or "application/octet-stream").partition("/")
        email_message.add_attachment(data, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=attachment.get("name"))
    return email_message


def _format_address(address: str | None, name: str | None) -> str:
    if address and name:
        return f'"{name}" <{address}>'
    return address or ""


def array_messages() -> list[dict[str, Any]]:
    return list(_array_log)


def reset_array() -> None:
    _array_log.clear()
