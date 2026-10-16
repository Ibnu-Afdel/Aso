"""`StartSession` through the real stack (T-18), using `tests/fixtures/session_app`.

Mirrors the `tests/test_spine_loop.py` fixture-app pattern: `sys.path` gets the fixture's root so
`bootstrap.app` and its sibling `config`/`routes` packages import, then `create_app()` builds a
real FastAPI app wired through `aso.foundation.stack`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "session_app"


@pytest.fixture
async def make_client(monkeypatch):
    """`await make_client(SESSION_DRIVER="array")` -> an `httpx2.AsyncClient` for a fresh app."""

    async def _make(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, str(value))
        sys.path.insert(0, str(FIXTURE))
        try:
            from bootstrap.app import create_app

            app = create_app()
        finally:
            sys.path.remove(str(FIXTURE))
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    return _make


@pytest.fixture(autouse=True)
def _clear_array_store():
    from aso.session import clear_array_store

    clear_array_store()
    yield
    clear_array_store()


# ------------------------------------------------------------ cookie basics


async def test_sets_session_and_xsrf_cookies_on_first_visit(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        r = await client.get("/")
        assert r.status_code == 200
        assert "fg-session" in client.cookies
        assert "XSRF-TOKEN" in client.cookies


async def test_session_id_is_stable_across_requests(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        r1 = await client.get("/write")
        r2 = await client.get("/write")
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["hits"] == 2


async def test_data_persists_across_requests_array_driver(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        await client.get("/write")
        await client.get("/write")
        r = await client.get("/write")
        assert r.json()["hits"] == 3


async def test_tampered_session_cookie_starts_a_new_session(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        r1 = await client.get("/write")
        sid1 = r1.json()["id"]
        cookie_value = client.cookies.get("fg-session")
        i = len(cookie_value) - 5  # the last base64 character may only carry padding bits
        tampered = cookie_value[:i] + ("a" if cookie_value[i] != "a" else "b") + cookie_value[i + 1 :]
        # Set the raw header directly for this one request: httpx2's cookie jar can otherwise
        # keep both the original and the replacement around (keyed by differing default
        # domains) and send the still-valid one, masking the tamper.
        r2 = await client.get("/write", headers={"Cookie": f"fg-session={tampered}"})
        assert r2.status_code == 200
        assert r2.json()["id"] != sid1
        assert r2.json()["hits"] == 1  # a brand new session, not an error


# ------------------------------------------------------------ previous url


async def test_previous_url_captured_on_get_200(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        await client.get("/write")
        r = await client.get("/previous")
        assert r.json()["previous_url"] == "/write"


async def test_previous_url_not_captured_for_prefetch(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        await client.get("/write")
        await client.get("/write", headers={"Purpose": "prefetch"})
        r = await client.get("/previous")
        # the prefetch request must not have overwritten "_previous_url" with its own path
        assert r.json()["previous_url"] == "/write"


# ------------------------------------------------------------ flash hand-off via the raw session


async def test_flash_visible_next_request_then_gone(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        await client.get("/flash-now")
        r1 = await client.get("/read-flash")
        assert r1.json()["notice"] == "hello"
        r2 = await client.get("/read-flash")
        assert r2.json()["notice"] is None


# ------------------------------------------------------------ regenerate / invalidate


async def test_regenerate_changes_session_id_keeps_data(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        w1 = await client.get("/write")
        old_id = w1.json()["id"]
        r = await client.post("/regenerate", headers={"X-XSRF-TOKEN": client.cookies["XSRF-TOKEN"]})
        assert r.json()["id"] != old_id
        w2 = await client.get("/write")
        assert w2.json()["hits"] == 2  # data (hit counter) survived regeneration


async def test_invalidate_changes_session_id_and_clears_data(make_client) -> None:
    async with await make_client(SESSION_DRIVER="array") as client:
        await client.get("/write")
        await client.get("/write")
        r = await client.post("/invalidate", headers={"X-XSRF-TOKEN": client.cookies["XSRF-TOKEN"]})
        assert r.status_code == 200
        w = await client.get("/write")
        assert w.json()["hits"] == 1  # counter reset: old data was flushed


# ------------------------------------------------------------ cookie driver, end to end


async def test_cookie_driver_persists_data_without_server_state(make_client) -> None:
    async with await make_client(SESSION_DRIVER="cookie") as client:
        r1 = await client.get("/write")
        assert r1.json()["hits"] == 1
        r2 = await client.get("/write")
        assert r2.json()["hits"] == 2
        assert "fg-session" in client.cookies
        # the cookie's own content changes every write (it carries the data itself).


async def test_cookie_driver_rejects_oversized_payload(make_client) -> None:
    async with await make_client(SESSION_DRIVER="cookie") as client:
        r = await client.get("/stuff/5000")
        assert r.status_code == 500


async def test_database_driver_rejects_oversized_payload_is_fine_for_other_drivers(make_client) -> None:
    # the 4000-byte cookie limit is specific to the `cookie` driver; other drivers do not care.
    async with await make_client(SESSION_DRIVER="array") as client:
        r = await client.get("/stuff/5000")
        assert r.status_code == 200
