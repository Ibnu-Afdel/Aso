"""`Mail`: `Mail.to(...).cc().bcc().send(mailable)` / `.queue(mailable)`, and `Mail.fake()` (T-41).

`queue()` renders right now, in the current request, and queues only the finished message (D-028)
-- so a mailable may take model instances as constructor arguments even when queued.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from fastogram.mail.mailable import Attachment, Mailable


def _normalize(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            out.extend(_normalize(item))
        return out
    email = getattr(value, "email", None)
    if email:
        return [email]
    raise TypeError(f"Mail.to()/.cc()/.bcc() cannot resolve an email address from {value!r}.")


@dataclass
class _Rendered:
    subject: str
    from_address: dict[str, str]
    reply_to: list[str]
    html: str | None
    text: str | None
    attachments: list[Attachment]


def _render(mailable: Mailable) -> _Rendered:
    from fastogram.mail.drivers import default_from_address
    from fastogram.mail.rendering import html_to_text

    envelope = mailable.envelope()
    content = mailable.content()
    html = None
    if content.view:
        from fastogram.mail.rendering import render_view

        html = render_view(content.view, content.with_)
    text = content.text
    if text is None and html is not None:
        text = html_to_text(html)

    if envelope.from_ is None:
        from_address = default_from_address()
    elif isinstance(envelope.from_, str):
        from_address = {"address": envelope.from_, "name": default_from_address().get("name", "")}
    else:
        address, name = envelope.from_
        from_address = {"address": address, "name": name}

    reply_to = envelope.reply_to
    reply_to_list = [reply_to] if isinstance(reply_to, str) else list(reply_to or [])

    return _Rendered(
        subject=envelope.subject,
        from_address=from_address,
        reply_to=reply_to_list,
        html=html,
        text=text,
        attachments=mailable.attachments(),
    )


def _to_wire(to: list[str], cc: list[str], bcc: list[str], rendered: _Rendered) -> dict[str, Any]:
    return {
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "from": rendered.from_address,
        "reply_to": rendered.reply_to,
        "subject": rendered.subject,
        "html": rendered.html,
        "text": rendered.text,
        "attachments": [a.to_wire() for a in rendered.attachments],
    }


@dataclass
class SentMail:
    """One `Mail.fake()` record. `Mail.assert_sent(Cls, lambda mail: mail.has_to(...))` passes
    this as `mail`; unknown attributes fall through to the original `Mailable` instance."""

    mailable: Mailable
    to: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    queued: bool

    def has_to(self, address: str) -> bool:
        return address in self.to

    def has_cc(self, address: str) -> bool:
        return address in self.cc

    def has_bcc(self, address: str) -> bool:
        return address in self.bcc

    def has_subject(self, subject: str) -> bool:
        return self.subject == subject

    def __getattr__(self, name: str) -> Any:
        return getattr(self.mailable, name)


class PendingMail:
    """Returned by `Mail.to(...)`; chain `.cc()`/`.bcc()` before `.send()`/`.queue()`."""

    def __init__(self, to: Any) -> None:
        self._to = _normalize(to)
        self._cc: list[str] = []
        self._bcc: list[str] = []

    def cc(self, address: Any) -> PendingMail:
        self._cc.extend(_normalize(address))
        return self

    def bcc(self, address: Any) -> PendingMail:
        self._bcc.extend(_normalize(address))
        return self

    async def send(self, mailable: Mailable) -> None:
        rendered = _render(mailable)
        if Mail._fake:
            Mail._sent.append(SentMail(mailable, self._to, self._cc, self._bcc, rendered.subject, queued=False))
            return
        from fastogram.mail.drivers import deliver_message

        message = _to_wire(self._to, self._cc, self._bcc, rendered)
        await deliver_message(message)

    async def queue(self, mailable: Mailable) -> None:
        rendered = _render(mailable)  # D-028: render now, queue only the finished message
        if Mail._fake:
            Mail._queued.append(SentMail(mailable, self._to, self._cc, self._bcc, rendered.subject, queued=True))
            return
        from fastogram.mail.queued_mail import SendQueuedMail

        message = _to_wire(self._to, self._cc, self._bcc, rendered)
        await SendQueuedMail(message=message).dispatch()


class Mail:
    """`Mail.to(...)`, plus `Mail.fake()` and class-level assertions (T-41)."""

    _fake: ClassVar[bool] = False
    _sent: ClassVar[list[SentMail]] = []
    _queued: ClassVar[list[SentMail]] = []

    @staticmethod
    def to(address: Any) -> PendingMail:
        return PendingMail(address)

    @classmethod
    def fake(cls) -> None:
        Mail._fake = True
        Mail._sent = []
        Mail._queued = []

    @classmethod
    def reset(cls) -> None:
        Mail._fake = False
        Mail._sent = []
        Mail._queued = []

    @classmethod
    def assert_sent(cls, mailable_cls: type[Mailable], check: Any = None) -> None:
        matches = [m for m in Mail._sent if isinstance(m.mailable, mailable_cls) and (check is None or check(m))]
        assert matches, f"The mailable [{mailable_cls.__name__}] was not sent."

    @classmethod
    def assert_sent_times(cls, mailable_cls: type[Mailable], times: int) -> None:
        matches = [m for m in Mail._sent if isinstance(m.mailable, mailable_cls)]
        assert len(matches) == times, (
            f"The mailable [{mailable_cls.__name__}] was sent {len(matches)} time(s), expected {times}."
        )

    @classmethod
    def assert_not_sent(cls, mailable_cls: type[Mailable], check: Any = None) -> None:
        matches = [m for m in Mail._sent if isinstance(m.mailable, mailable_cls) and (check is None or check(m))]
        assert not matches, f"The mailable [{mailable_cls.__name__}] was sent."

    @classmethod
    def assert_nothing_sent(cls) -> None:
        assert not Mail._sent, f"{len(Mail._sent)} mailable(s) were sent."

    @classmethod
    def assert_queued(cls, mailable_cls: type[Mailable], check: Any = None) -> None:
        matches = [m for m in Mail._queued if isinstance(m.mailable, mailable_cls) and (check is None or check(m))]
        assert matches, f"The mailable [{mailable_cls.__name__}] was not queued."

    @classmethod
    def assert_nothing_queued(cls) -> None:
        assert not Mail._queued, f"{len(Mail._queued)} mailable(s) were queued."


def reset_mail() -> None:
    """Test isolation: `Mail.reset()` plus clear the `array` transport's recorded messages."""
    Mail.reset()
    from fastogram.mail.drivers import reset_array

    reset_array()
