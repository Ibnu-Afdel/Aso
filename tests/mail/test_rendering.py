"""`html_to_text()`: the plain-text fallback generated from HTML (T-41, open question 1)."""

from __future__ import annotations

from aso.mail.rendering import html_to_text


def test_strips_tags():
    assert html_to_text("<p>Hello <strong>world</strong></p>") == "Hello world"


def test_keeps_links_as_text_and_url():
    assert html_to_text('<a href="https://example.com">Visit us</a>') == "Visit us (https://example.com)"


def test_link_without_text_is_dropped_but_href_without_text_is_too():
    assert html_to_text('<a href="https://example.com"></a>after') == "after"


def test_block_tags_become_newlines():
    html = "<p>One</p><p>Two</p>"
    assert html_to_text(html) == "One\nTwo"


def test_br_becomes_a_newline():
    assert html_to_text("Line one<br>Line two") == "Line one\nLine two"


def test_style_and_script_contents_are_skipped():
    html = "<style>body{color:red}</style><p>Visible</p><script>evil()</script>"
    assert html_to_text(html) == "Visible"


def test_excess_blank_lines_are_collapsed():
    html = "<p>A</p><br><br><br><p>B</p>"
    text = html_to_text(html)
    assert "\n\n\n" not in text
    assert text == "A\n\nB"
