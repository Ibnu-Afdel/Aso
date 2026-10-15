"""`Mail.fake()` + class-level assertions (T-41)."""

from __future__ import annotations

import pytest

from fastogram.mail import Content, Envelope, Mail, Mailable


class _Greeting(Mailable):
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email

    def envelope(self) -> Envelope:
        return Envelope(subject=f"Hi {self.name}")

    def content(self) -> Content:
        return Content(text=f"Hello, {self.name}.")


async def test_fake_records_sent_mail_instead_of_delivering():
    Mail.fake()

    await Mail.to("ada@example.com").send(_Greeting("Ada", "ada@example.com"))

    Mail.assert_sent(_Greeting)
    Mail.assert_sent(_Greeting, lambda mail: mail.has_to("ada@example.com"))
    Mail.assert_sent_times(_Greeting, 1)


async def test_fake_records_queued_mail_separately_from_sent_mail():
    Mail.fake()

    await Mail.to("ada@example.com").queue(_Greeting("Ada", "ada@example.com"))

    Mail.assert_queued(_Greeting)
    Mail.assert_nothing_sent()


async def test_recorded_mail_exposes_has_to_has_cc_has_subject():
    Mail.fake()

    await Mail.to("ada@example.com").cc("cc@example.com").send(_Greeting("Ada", "ada@example.com"))

    Mail.assert_sent(
        _Greeting,
        lambda mail: mail.has_to("ada@example.com") and mail.has_cc("cc@example.com") and mail.has_subject("Hi Ada"),
    )


async def test_recorded_mail_has_bcc_too():
    Mail.fake()

    await Mail.to("ada@example.com").bcc("bcc@example.com").send(_Greeting("Ada", "ada@example.com"))

    Mail.assert_sent(_Greeting, lambda mail: mail.has_bcc("bcc@example.com"))


async def test_recorded_mail_falls_through_to_the_underlying_mailable():
    """Unknown attributes fall through to the original `Mailable` instance (mail/manager.py's
    `SentMail.__getattr__`)."""
    Mail.fake()

    await Mail.to("ada@example.com").send(_Greeting("Ada", "ada@example.com"))

    Mail.assert_sent(_Greeting, lambda mail: mail.name == "Ada")


async def test_assert_not_sent():
    Mail.fake()
    Mail.assert_not_sent(_Greeting)
    await Mail.to("a@example.com").send(_Greeting("Ada", "a@example.com"))
    with pytest.raises(AssertionError):
        Mail.assert_not_sent(_Greeting)


async def test_assert_nothing_sent():
    Mail.fake()
    Mail.assert_nothing_sent()
    await Mail.to("a@example.com").send(_Greeting("Ada", "a@example.com"))
    with pytest.raises(AssertionError):
        Mail.assert_nothing_sent()


async def test_assert_nothing_queued():
    Mail.fake()
    Mail.assert_nothing_queued()
    await Mail.to("a@example.com").queue(_Greeting("Ada", "a@example.com"))
    with pytest.raises(AssertionError):
        Mail.assert_nothing_queued()


async def test_assert_sent_fails_when_not_sent():
    Mail.fake()
    with pytest.raises(AssertionError):
        Mail.assert_sent(_Greeting)


async def test_assert_sent_times_fails_on_mismatch():
    Mail.fake()
    await Mail.to("a@example.com").send(_Greeting("Ada", "a@example.com"))
    with pytest.raises(AssertionError):
        Mail.assert_sent_times(_Greeting, 2)


async def test_assert_queued_fails_when_not_queued():
    Mail.fake()
    with pytest.raises(AssertionError):
        Mail.assert_queued(_Greeting)
