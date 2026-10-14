"""End-to-end tests for controller return-value conversion (T-13, T-15): the full "What
controllers return" table, via `ConvertController`."""

from __future__ import annotations

import httpx2 as httpx


async def test_dict_with_mixed_types_is_jsonable(client: httpx.AsyncClient):
    r = await client.get("/convert/dict")
    assert r.status_code == 200
    body = r.json()
    assert body["when"] == "2026-01-02T03:04:05+00:00"
    assert body["amount"] == "9.95"
    assert body["id"] == "12345678-1234-5678-1234-567812345678"
    assert body["status"] == "open"


async def test_list_becomes_a_json_array(client: httpx.AsyncClient):
    r = await client.get("/convert/list")
    assert r.status_code == 200
    assert r.json() == [1, 2, 3]


async def test_none_becomes_204(client: httpx.AsyncClient):
    r = await client.get("/convert/none")
    assert r.status_code == 204


async def test_a_starlette_response_is_sent_as_is(client: httpx.AsyncClient):
    r = await client.get("/convert/response")
    assert r.status_code == 200
    assert r.text == "plain"
    assert r.headers["content-type"].startswith("text/plain")


async def test_a_model_instance_is_serialised_via_to_dict(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    r = await client.post("/convert/model", headers={"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Converted"
    assert body["slug"] == "converted"
    assert "id" in body


async def test_a_pydantic_model_is_dumped(client: httpx.AsyncClient):
    r = await client.get("/convert/pydantic")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
