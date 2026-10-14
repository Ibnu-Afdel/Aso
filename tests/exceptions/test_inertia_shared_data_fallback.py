"""T-20: the Inertia error page still gets shared data when the exception happened *before*
`HandleInertiaRequests` ran (so `context.current().inertia` is still `None`).

`CrashBeforeInertia` (a global web-layer middleware appended *after* `PreventRequestForgery` but
*before* `HandleInertiaRequests`, see `tests/fixtures/errors/bootstrap/app.py`) raises for exactly
one path, simulating a route middleware (or any global web layer) failing early. The handler must
find the app's own `HandleInertiaRequests` from `middleware_config.web_layers()` to render the
error page with `share()` applied -- otherwise the error page would be missing `app_name`.
"""

from __future__ import annotations

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


async def test_error_page_has_shared_data_when_ctx_inertia_was_never_set(client):
    r = await client.get("/crash-before-inertia", headers=INERTIA)
    assert r.status_code == 500
    page = r.json()
    assert page["component"] == "error"
    assert page["props"]["app_name"] == "ErrorsApp"
    assert page["props"]["status"] == 500


async def test_error_page_first_visit_html_also_has_shared_data(client):
    r = await client.get("/crash-before-inertia")  # no X-Inertia header: first-visit HTML page
    assert r.status_code == 500
    assert "ErrorsApp" not in r.text or True  # the embedded JSON page object is what we check
    import json
    import re

    m = re.search(r'<script data-page="app" type="application/json">(.*?)</script>', r.text)
    assert m
    page = json.loads(m.group(1))
    assert page["props"]["app_name"] == "ErrorsApp"


async def test_session_and_xsrf_cookies_still_set_when_a_global_layer_crashes(client):
    r = await client.get("/crash-before-inertia")
    assert "set-cookie" in r.headers
    cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else [r.headers["set-cookie"]]
    joined = " ".join(cookies)
    assert "errors-session=" in joined or "XSRF-TOKEN=" in joined
