"""`Mail.to(...).cc().bcc().send()/.queue()` (T-41, D-028)."""

from __future__ import annotations

import pytest

from fastogram.mail import Content, Envelope, Mail, Mailable, SendQueuedMail
from fastogram.queue import Queue


class _Greeting(Mailable):
    def __init__(self, name: str) -> None:
        self.name = name

    def envelope(self) -> Envelope:
        return Envelope(subject=f"Hi {self.name}")

    def content(self) -> Content:
        return Content(text=f"Hello, {self.name}.")


class _User:
    def __init__(self, email: str) -> None:
        self.email = email


# ------------------------------------------------------------ Mail.to() address resolution


def test_to_accepts_a_plain_string():
    pending = Mail.to("a@example.com")
    assert pending._to == ["a@example.com"]


def test_to_accepts_a_list_of_strings():
    pending = Mail.to(["a@example.com", "b@example.com"])
    assert pending._to == ["a@example.com", "b@example.com"]


def test_to_accepts_a_model_with_an_email_attribute():
    pending = Mail.to(_User("a@example.com"))
    assert pending._to == ["a@example.com"]


def test_to_accepts_a_list_of_models():
    pending = Mail.to([_User("a@example.com"), _User("b@example.com")])
    assert pending._to == ["a@example.com", "b@example.com"]


def test_to_rejects_something_with_no_email():
    with pytest.raises(TypeError):
        Mail.to(object())


def test_cc_and_bcc_chain_and_accumulate():
    pending = Mail.to("a@example.com").cc("c1@example.com").cc(["c2@example.com"]).bcc("b@example.com")
    assert pending._cc == ["c1@example.com", "c2@example.com"]
    assert pending._bcc == ["b@example.com"]


# ------------------------------------------------------------ send()


async def test_send_renders_and_delivers_the_wire_message(monkeypatch):
    captured = {}

    async def fake_deliver(message, mailer=None):
        captured["message"] = message
        captured["mailer"] = mailer

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    await Mail.to("a@example.com").cc("c@example.com").send(_Greeting("Ada"))

    message = captured["message"]
    assert message["to"] == ["a@example.com"]
    assert message["cc"] == ["c@example.com"]
    assert message["bcc"] == []
    assert message["subject"] == "Hi Ada"
    assert message["html"] is None
    assert message["text"] == "Hello, Ada."
    assert message["attachments"] == []
    assert message["from"]["address"]


async def test_send_generates_text_from_html_when_no_text_is_given(monkeypatch, tmp_path):
    captured = {}

    async def fake_deliver(message, mailer=None):
        captured["message"] = message

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    from fastogram.foundation import paths

    views = tmp_path / "resources" / "views" / "mail"
    views.mkdir(parents=True)
    (views / "note.html").write_text("<p>Hi <b>Ada</b></p>")
    paths.set_base_path(tmp_path)

    class ViewMail(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(view="mail/note.html")

    await Mail.to("a@example.com").send(ViewMail())

    message = captured["message"]
    assert message["html"] == "<p>Hi <b>Ada</b></p>"
    assert message["text"] == "Hi Ada"


async def test_envelope_from_as_string_uses_the_configured_from_name(monkeypatch):
    monkeypatch.setattr(
        "fastogram.mail.drivers.default_from_address", lambda: {"address": "default@x.com", "name": "Default"}
    )
    captured = {}

    async def fake_deliver(message, mailer=None):
        captured["message"] = message

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    class FromString(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi", from_="custom@x.com")

        def content(self) -> Content:
            return Content(text="hi")

    await Mail.to("a@example.com").send(FromString())

    assert captured["message"]["from"] == {"address": "custom@x.com", "name": "Default"}


async def test_envelope_from_as_tuple_overrides_both_address_and_name(monkeypatch):
    captured = {}

    async def fake_deliver(message, mailer=None):
        captured["message"] = message

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    class FromTuple(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi", from_=("custom@x.com", "Custom"))

        def content(self) -> Content:
            return Content(text="hi")

    await Mail.to("a@example.com").send(FromTuple())

    assert captured["message"]["from"] == {"address": "custom@x.com", "name": "Custom"}


async def test_reply_to_string_is_normalized_to_a_list(monkeypatch):
    captured = {}

    async def fake_deliver(message, mailer=None):
        captured["message"] = message

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    class WithReplyTo(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi", reply_to="support@x.com")

        def content(self) -> Content:
            return Content(text="hi")

    await Mail.to("a@example.com").send(WithReplyTo())

    assert captured["message"]["reply_to"] == ["support@x.com"]


# ------------------------------------------------------------ queue() (D-028)


async def test_queue_renders_now_and_dispatches_send_queued_mail():
    """"`queue()` renders the mail right away ... and queues the finished message" (T-41)."""
    Queue.fake()

    await Mail.to("a@example.com").queue(_Greeting("Ada"))

    Queue.assert_dispatched_times(SendQueuedMail, 1)
    job = Queue._dispatched[0][1]
    assert job.message["to"] == ["a@example.com"]
    assert job.message["subject"] == "Hi Ada"
    assert job.message["text"] == "Hello, Ada."
    assert job.after_commit is True


async def test_queue_strips_any_model_the_mailable_held_down_to_plain_json():
    """D-028: nothing but strings reaches the queue, even though the mailable's constructor took
    a non-serialisable object -- because it is rendered (to a dict of strings) before dispatch."""
    Queue.fake()

    class HeldModel:
        def __init__(self, name: str) -> None:
            self.name = name

    class WithModel(Mailable):
        def __init__(self, model: HeldModel) -> None:
            self.model = model

        def envelope(self) -> Envelope:
            return Envelope(subject=f"Hi {self.model.name}")

        def content(self) -> Content:
            return Content(text=f"Hello, {self.model.name}.")

    await Mail.to("a@example.com").queue(WithModel(HeldModel("Ada")))

    job = Queue._dispatched[0][1]
    from fastogram.queue.serialization import validate_serializable

    validate_serializable(job.message)  # must not raise: the job payload is plain JSON


async def test_send_does_not_validate_serializability_it_sends_immediately(monkeypatch):
    """`.send()` is not a job: it may hold a model and still deliver right away."""

    async def fake_deliver(message, mailer=None):
        pass

    monkeypatch.setattr("fastogram.mail.drivers.deliver_message", fake_deliver)

    class Holder:
        pass

    class WithObject(Mailable):
        def __init__(self, obj: Holder) -> None:
            self.obj = obj

        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(text="hi")

    await Mail.to("a@example.com").send(WithObject(Holder()))  # must not raise
