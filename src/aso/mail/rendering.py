"""Jinja rendering for mail views (T-41), and the HTML->text fallback.

Templates are looked up in the app's `resources/views/` first (so `app/mail/welcome_mail.py` ->
`content(view="mail/welcome.html")` finds `resources/views/mail/welcome.html`), falling back to
this package's own `resources/views/mail/layout.html` when the app has not supplied one -- the
"minimal built-in layout" the T-41 page ships. Mirrors `aso.inertia.root`'s environment.
"""

from __future__ import annotations

import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

_BUILTIN_VIEWS = Path(__file__).parent / "resources" / "views"


@lru_cache(maxsize=4)
def _environment(views_dir: str) -> Environment:
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(views_dir), FileSystemLoader(str(_BUILTIN_VIEWS))]),
        autoescape=select_autoescape(["html", "xml"]),
    )
    try:
        from aso.config import config

        env.globals["config"] = config
    except ImportError:  # pragma: no cover - config always importable in practice
        pass
    try:
        from aso.routing import route

        env.globals["route"] = route
    except ImportError:  # pragma: no cover - routing not booted (unit tests of rendering alone)
        pass
    return env


def render_view(view: str, data: dict[str, Any]) -> str:
    from aso.foundation.paths import resource_path

    env = _environment(str(resource_path("views")))
    template = env.get_template(view)
    return template.render(**data)


class _TextExtractor(HTMLParser):
    """Strips tags; keeps `<a href="url">text</a>` as `text (url)` (T-41)."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._skip_depth += 1
        elif tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_text = []
        elif tag in ("br", "p", "div", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script"):
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "a":
            text = "".join(self._link_text).strip()
            if self._link_href and text:
                self._parts.append(f"{text} ({self._link_href})")
            elif text:
                self._parts.append(text)
            self._link_href = None
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._link_href is not None:
            self._link_text.append(data)
        else:
            self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n[ \t]*", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.text()
