"""`Mail.to(...).queue()` follows the T-42 job rules: `SendQueuedMail.after_commit = True`
(T-41, D-028), so mail queued inside `DB.transaction()` is only delivered after the commit."""

from __future__ import annotations

from fastogram.database.db import DB
from fastogram.mail import Content, Envelope, Mail, Mailable


class _Greeting(Mailable):
    def __init__(self, name: str) -> None:
        self.name = name

    def envelope(self) -> Envelope:
        return Envelope(subject=f"Hi {self.name}")

    def content(self) -> Content:
        return Content(text=f"Hello, {self.name}.")


async def test_queued_mail_waits_for_the_enclosing_transaction_to_commit(db, monkeypatch):
    delivered = []

    async def fake_deliver(message, mailer=None):
        delivered.append(message)

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    async with DB.transaction():
        await Mail.to("ada@example.com").queue(_Greeting("Ada"))
        assert delivered == [], "SendQueuedMail.after_commit = True (D-028)"

    assert len(delivered) == 1
    assert delivered[0]["to"] == ["ada@example.com"]


async def test_queued_mail_never_delivered_if_the_transaction_rolls_back(db, monkeypatch):
    delivered = []

    async def fake_deliver(message, mailer=None):
        delivered.append(message)

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    class Boom(Exception):
        pass

    try:
        async with DB.transaction():
            await Mail.to("ada@example.com").queue(_Greeting("Ada"))
            raise Boom
    except Boom:
        pass

    assert delivered == []
