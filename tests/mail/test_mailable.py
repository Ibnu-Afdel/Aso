"""`Mailable`, `Envelope`, `Content`, `Attachment` (T-41)."""

from __future__ import annotations

import base64

import pytest

from fastogram.mail import Attachment, Content, Envelope, Mailable


def test_mailable_without_envelope_or_content_raises_not_implemented():
    class Bare(Mailable):
        pass

    with pytest.raises(NotImplementedError):
        Bare().envelope()
    with pytest.raises(NotImplementedError):
        Bare().content()


def test_mailable_attachments_default_to_empty():
    class Plain(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(text="hi")

    assert Plain().attachments() == []


def test_render_uses_content_text_when_there_is_no_view():
    class TextOnly(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(text="Plain body")

    assert TextOnly().render() == "Plain body"


def test_render_with_no_view_and_no_text_is_empty_string():
    class Empty(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content()

    assert Empty().render() == ""


def test_render_compiles_the_jinja_view_with_with_data(tmp_path):
    from fastogram.foundation import paths

    views = tmp_path / "resources" / "views"
    (views / "mail").mkdir(parents=True)
    (views / "mail" / "greet.html").write_text("Hello {{ name }}!")
    paths.set_base_path(tmp_path)

    class Greeting(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(view="mail/greet.html", with_={"name": "Ada"})

    assert Greeting().render() == "Hello Ada!"


def test_render_falls_back_to_the_built_in_layout_when_the_app_has_none(tmp_path):
    """"falling back to this package's own `resources/views/mail/layout.html` when the app has
    not supplied one" (mail/rendering.py)."""
    from fastogram.foundation import paths

    views = tmp_path / "resources" / "views"
    (views / "mail").mkdir(parents=True)
    (views / "mail" / "notice.html").write_text(
        "{% extends 'mail/layout.html' %}{% block content %}<p>Hi there</p>{% endblock %}"
    )
    paths.set_base_path(tmp_path)

    class Notice(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(view="mail/notice.html")

    html = Notice().render()
    assert "<p>Hi there</p>" in html
    assert "All rights reserved" in html  # from the built-in layout.html footer


def test_render_prefers_the_apps_own_layout_over_the_built_in_one(tmp_path):
    from fastogram.foundation import paths

    views = tmp_path / "resources" / "views"
    (views / "mail").mkdir(parents=True)
    (views / "mail" / "layout.html").write_text("APP-LAYOUT[{% block content %}{% endblock %}]")
    (views / "mail" / "notice.html").write_text(
        "{% extends 'mail/layout.html' %}{% block content %}X{% endblock %}"
    )
    paths.set_base_path(tmp_path)

    class Notice(Mailable):
        def envelope(self) -> Envelope:
            return Envelope(subject="hi")

        def content(self) -> Content:
            return Content(view="mail/notice.html")

    assert Notice().render() == "APP-LAYOUT[X]"


# ------------------------------------------------------------ Attachment


def test_attachment_from_path_reads_bytes_and_resolves_the_name(tmp_path):
    file_path = tmp_path / "invoice.pdf"
    file_path.write_bytes(b"%PDF-1.4 fake")

    attachment = Attachment.from_path(file_path)

    assert attachment.read() == b"%PDF-1.4 fake"
    assert attachment.resolved_name() == "invoice.pdf"


def test_attachment_from_path_accepts_an_explicit_name():
    attachment = Attachment(path=None, data=b"hi", name="custom.txt")
    assert attachment.resolved_name() == "custom.txt"


def test_attachment_from_data_round_trips():
    attachment = Attachment.from_data(b"hello", "greeting.txt", content_type="text/plain")

    assert attachment.read() == b"hello"
    assert attachment.resolved_name() == "greeting.txt"
    assert attachment.content_type == "text/plain"


def test_attachment_without_path_or_data_raises_on_read():
    with pytest.raises(ValueError, match="path.*data"):
        Attachment().read()


def test_attachment_resolved_name_falls_back_to_a_generic_name():
    assert Attachment(data=b"x").resolved_name() == "attachment"


def test_attachment_to_wire_is_json_safe_and_base64_round_trips():
    attachment = Attachment.from_data(b"hello world", "note.txt", content_type="text/plain")

    wire = attachment.to_wire()

    assert wire["name"] == "note.txt"
    assert wire["content_type"] == "text/plain"
    assert base64.b64decode(wire["data_b64"]) == b"hello world"
