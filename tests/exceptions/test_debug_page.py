"""The debug page renders without raising and never leaks cookie/authorization values (T-20)."""

from __future__ import annotations

from starlette.requests import Request

from aso.exceptions import debug


def _request() -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/boom", "query_string": b"", "scheme": "http",
        "server": ("testserver", 80), "headers": [(b"cookie", b"secret-session"), (b"authorization", b"Bearer t"), (b"accept", b"text/html")],
    })


def test_debug_page_shows_exception_and_redacts_secrets() -> None:
    try:
        raise RuntimeError("it broke <here>")
    except RuntimeError as exc:
        page = debug.render(_request(), exc)
    assert "RuntimeError" in page and "it broke &lt;here&gt;" in page
    assert "test_debug_page.py" in page
    assert "secret-session" not in page and "Bearer t" not in page
    assert "[redacted]" in page
