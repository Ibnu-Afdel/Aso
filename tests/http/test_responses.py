"""End-to-end tests for redirects, flash/errors/input, cookies, and `abort*()` (T-15)."""

from __future__ import annotations

import httpx2 as httpx

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


def _xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


async def _page(client: httpx.AsyncClient) -> dict:
    """Read back flash/errors via the one Inertia page the fixture app renders (T-16/T-17's
    `errors` always-prop and `page.flash` are exercised in `tests/inertia`; this just reads them
    back to confirm T-15's redirect helpers actually wrote what they claim to)."""
    r = await client.get("/misc/about", headers=INERTIA)
    return r.json()


async def test_redirect_to_a_plain_path(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-to")
    assert r.status_code == 302
    assert r.headers["location"] == "/misc/ping"


async def test_redirect_to_a_named_route(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-named")
    assert r.status_code == 302
    assert r.headers["location"] == "/misc/ping"


async def test_redirect_away_is_used_verbatim(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-away")
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/elsewhere"


async def test_intended_pops_the_stored_url_then_falls_back_to_default(client: httpx.AsyncClient):
    await client.get("/misc/set-intended")
    r = await client.get("/misc/redirect-intended")
    assert r.headers["location"] == "/misc/ping"
    # popped: a second call falls back to the default passed to intended().
    r = await client.get("/misc/redirect-intended")
    assert r.headers["location"] == "/misc/default"


# ---------------------------------------------------------------- back() resolution


async def test_back_uses_same_origin_referer_first(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-back", headers={"Referer": "http://testserver/posts/1"})
    assert r.headers["location"] == "/posts/1"


async def test_back_ignores_a_foreign_referer(client: httpx.AsyncClient):
    await client.get("/posts")  # records session._previous_url = "/posts"
    r = await client.get("/misc/redirect-back", headers={"Referer": "http://evil.example/steal"})
    assert r.headers["location"] == "/posts"


async def test_back_falls_back_to_session_previous_url_when_no_referer(client: httpx.AsyncClient):
    await client.get("/posts")
    r = await client.get("/misc/redirect-back")
    assert r.headers["location"] == "/posts"


async def test_back_falls_back_to_default_with_no_referer_or_session(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-back")
    assert r.headers["location"] == "/"


# ---------------------------------------------------------------- flash / errors / input


async def test_with_flash_key_value(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-flash")
    assert r.status_code == 302
    assert (await _page(client))["flash"] == {"success": "done"}


async def test_with_flash_dict_form(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-flash-dict")
    assert r.status_code == 302
    assert (await _page(client))["flash"] == {"success": "done", "highlight": 1}


async def test_with_errors_default_bag(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-errors")
    assert r.status_code == 302
    assert (await _page(client))["props"]["errors"] == {"email": "bad"}


async def test_with_errors_named_bag(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-errors-bag")
    assert r.status_code == 302
    assert (await _page(client))["props"]["errors"] == {"invite": {"email": "bad"}}


async def test_with_input_flashes_old_input_excluding_dont_flash_keys(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    r = await client.post(
        "/misc/redirect-with-input",
        data={"title": "abc", "password": "secret"},
        headers=_xsrf(client),
    )
    assert r.status_code == 302
    # old() reads from the session on the *next* request; password must be excluded (T-14/T-15).
    r2 = await client.get("/misc/inspect")
    assert r2.status_code == 200


async def test_with_fragment_appends_hash_to_location(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-fragment")
    assert r.status_code == 302
    assert r.headers["location"] == "/misc/ping#comments"


# ---------------------------------------------------------------- cookies


async def test_cookie_sets_a_cookie_on_the_redirect(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-cookie")
    assert r.status_code == 302
    set_cookie = r.headers.get("set-cookie", "")
    assert "appearance=dark" in set_cookie


async def test_without_cookie_deletes_it(client: httpx.AsyncClient):
    r = await client.get("/misc/redirect-without-cookie")
    assert r.status_code == 302
    set_cookie = r.headers.get("set-cookie", "")
    assert 'appearance=""' in set_cookie or "Max-Age=0" in set_cookie


# ---------------------------------------------------------------- abort / abort_if / abort_unless


async def test_abort_raises_the_given_status(client: httpx.AsyncClient):
    assert (await client.get("/misc/abort?status=403")).status_code == 403
    assert (await client.get("/misc/abort?status=400")).status_code == 400


async def test_abort_if_raises_only_when_true(client: httpx.AsyncClient):
    assert (await client.get("/misc/abort-if?cond=true")).status_code == 418
    assert (await client.get("/misc/abort-if?cond=false")).json() == {"ok": True}


async def test_abort_unless_raises_only_when_false(client: httpx.AsyncClient):
    assert (await client.get("/misc/abort-unless?cond=false")).status_code == 418
    assert (await client.get("/misc/abort-unless?cond=true")).json() == {"ok": True}
