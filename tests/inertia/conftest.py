"""Fixture app plumbing for `tests/inertia/` (T-16, T-17, T-07).

Other packages' fixture apps (and this one) reuse the top-level module names `app`, `bootstrap`,
`routes`, `config`: real Python imports, cached in `sys.modules`. `config.*` and route files are
reloaded fresh by the framework itself (see `aso.config.load` and
`aso.routing.registry.load_routes`), but `app`/`bootstrap` are plain imports, so we purge
them from `sys.modules` before and after each test to avoid picking up another fixture app's
cached package of the same name.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "inertia_app"
_TOP_LEVEL = ("app", "bootstrap", "routes", "config")


def _purge() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in _TOP_LEVEL:
            del sys.modules[name]


@pytest.fixture
async def client():
    _purge()
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))
        _purge()


def page_from_html(html: str) -> dict:
    m = re.search(r'<script data-page="app" type="application/json">(.*?)</script>', html)
    assert m, html
    return json.loads(m.group(1))


INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


def xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
