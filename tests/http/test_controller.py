"""`Controller` / `ControllerMiddleware` (T-13): single-action controllers, instance-per-request,
and the public re-export of `fastogram.http.FormRequest`."""

from __future__ import annotations

import httpx2 as httpx

from fastogram.http import Controller, ControllerMiddleware, FormRequest
from fastogram.validation.form_request import FormRequest as ValidationFormRequest


def test_form_request_is_re_exported_from_fastogram_http():
    assert FormRequest is ValidationFormRequest


def test_controller_middleware_dataclass_defaults():
    entry = ControllerMiddleware("subscribed")
    assert entry.only is None
    assert entry.except_ is None


def test_controller_default_middleware_is_empty_list():
    assert Controller.middleware() == []


async def test_single_action_controller_is_invoked_via_dunder_call(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/invoke/42", headers=xsrf)
    assert r.status_code == 200
    assert r.json() == {"invoked": 42}


async def test_a_new_controller_instance_is_created_per_request(client: httpx.AsyncClient):
    """No shared mutable state leaks between requests to the same controller class."""
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r1 = await client.post("/invoke/1", headers=xsrf)
    r2 = await client.post("/invoke/2", headers=xsrf)
    assert r1.json() == {"invoked": 1}
    assert r2.json() == {"invoked": 2}
