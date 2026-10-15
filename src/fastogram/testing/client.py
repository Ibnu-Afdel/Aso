"""`TestClient` (T-56): `httpx2.AsyncClient` + `ASGITransport`, with Laravel-style fluent helpers.

**Scope-state injection.** `with_csrf()` and `without_middleware()` need to reach into the ASGI
`scope["state"]` dict before `RequestContextMiddleware` (the first global layer) creates it --
exactly the mechanism `session.forgery._force_csrf` already reads (`scope["state"]
["fastogram.force_csrf"]`). `ASGITransport` builds a fresh `scope` per call and gives us no hook
to inject extra keys, so this module wraps the real ASGI app once; the wrapper reads a
`contextvar` set by `_request()` immediately before calling `httpx2`, in the same `asyncio` task
(no task boundary crosses here), and merges it into `scope["state"]`.

**Session/exception capture.** `TestResponse` needs the session as it was saved and the
exception the handler reported, but by the time `AsyncClient.request()` returns, every layer's
`finally: context.leave(token)` has already unwound `fastogram.context`. The trick: every send
wrapper in the stack (CSRF, auth, `StartSession`) calls its *own* logic and then calls the `send`
it was given -- so by the time the outermost `send` (ours) receives `"http.response.start"`,
every inner layer has already run, but the request's `context.current()` is still live (we are
still nested inside the `await self.app(...)` call that will eventually return and trigger the
`finally` blocks). Capturing there gives us the final, persisted session.
"""

from __future__ import annotations

import contextvars
import time
from collections.abc import Mapping
from typing import Any

import httpx2

from fastogram.testing.options import PendingOptions
from fastogram.testing.response import TestResponse

__all__ = ["TestClient"]

_pending_scope_state: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "fastogram_testclient_scope_state", default=None
)
_pending_capture: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "fastogram_testclient_capture", default=None
)


class TestClient:
    """`TestClient(app)`: wraps the booted FastAPI app. Copies (returned by the fluent
    modifiers) share the same cookie jar and the same underlying `httpx2.AsyncClient`."""

    __test__ = False  # not a pytest test class, despite the name (T-56's public API name)

    def __init__(self, app: Any, *, base_url: str = "http://testserver") -> None:
        self._app = app
        self._state = PendingOptions()
        self._transport = httpx2.ASGITransport(app=self._dispatch)
        self._http = httpx2.AsyncClient(transport=self._transport, base_url=base_url, follow_redirects=False)

    # ------------------------------------------------------------ ASGI wrapper

    async def _dispatch(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        extra = _pending_scope_state.get()
        if extra:
            scope.setdefault("state", {}).update(extra)
        capture = _pending_capture.get()

        async def capturing_send(message: Mapping[str, Any]) -> None:
            if message["type"] == "http.response.start" and capture is not None:
                from fastogram import context

                ctx = context.current()
                if ctx is not None:
                    capture["session"] = dict(ctx.session.snapshot()) if ctx.session is not None else None
                    capture["exception"] = ctx.extras.get("testing.exception")
            await send(message)

        await self._app(scope, receive, capturing_send)

    # ------------------------------------------------------------ copies / fluent configuration

    def _copy(self, **overrides: Any) -> TestClient:
        new = TestClient.__new__(TestClient)
        new._app = self._app
        new._transport = self._transport
        new._http = self._http
        new._state = self._state.copy(**overrides)
        return new

    def acting_as(self, user: Any) -> TestClient:
        return self._copy(acting_as_user=user)

    def with_session(self, data: dict[str, Any]) -> TestClient:
        return self._copy(session_patch={**self._state.session_patch, **data})

    def from_url(self, url: str) -> TestClient:
        return self._copy(referer=url)

    def with_headers(self, headers: dict[str, str]) -> TestClient:
        return self._copy(headers={**self._state.headers, **headers})

    def with_cookie(self, name: str, value: str) -> TestClient:
        return self._copy(extra_cookies={**self._state.extra_cookies, name: value})

    def _read_cookie(self, name: str) -> str | None:
        """Read one cookie's value straight from the jar's entries, by name only.

        `httpx2.Cookies.get()` matches by `(name, domain, path)` and raises `CookieConflict`
        when more than one entry shares a name -- which happens here because our own writes
        (via the `cookies=` request kwarg, below) and the entries httpx records from a real
        `Set-Cookie` response end up filed under slightly different domains for a bare,
        dot-less test host like `testserver` (`http.cookiejar` rewrites an unqualified host's
        *effective* request host to `testserver.local` internally, SO a cookie we wrote against
        the literal host never matches a request's Cookie header, and `.get()` sees both as
        unrelated entries). Scanning the jar by name alone sidesteps that quirk entirely.
        """
        for cookie in self._http.cookies.jar:
            if cookie.name == name:
                return cookie.value
        return None

    def inertia(self, version: str | None = None) -> TestClient:
        return self._copy(inertia=True, inertia_version=version)

    def without_middleware(self, *aliases: str) -> TestClient:
        return self._copy(without_middleware=aliases or ("__all__",))

    def with_csrf(self) -> TestClient:
        return self._copy(force_csrf=True)

    def with_exception_handling(self, enabled: bool) -> TestClient:
        return self._copy(raise_exceptions=not enabled)

    def follow_redirects(self, value: bool = True) -> TestClient:
        return self._copy(follow=value)

    # ------------------------------------------------------------ requests

    async def get(self, url: str, params: dict[str, Any] | None = None, **kwargs: Any) -> TestResponse:
        return await self._request("GET", url, params=params, **kwargs)

    async def post(self, url: str, json: Any = None, data: Any = None, files: Any = None, **kwargs: Any) -> TestResponse:
        return await self._request("POST", url, json=json, data=data, files=files, **kwargs)

    async def put(self, url: str, json: Any = None, **kwargs: Any) -> TestResponse:
        return await self._request("PUT", url, json=json, **kwargs)

    async def patch(self, url: str, json: Any = None, **kwargs: Any) -> TestResponse:
        return await self._request("PATCH", url, json=json, **kwargs)

    async def delete(self, url: str, json: Any = None, **kwargs: Any) -> TestResponse:
        return await self._request("DELETE", url, json=json, **kwargs)

    async def post_json(self, url: str, data: Any = None, **kwargs: Any) -> TestResponse:
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        return await self._request("POST", url, json=data, headers=headers, **kwargs)

    # ------------------------------------------------------------ auth assertions

    async def _current_session(self) -> dict[str, Any]:
        from fastogram.session.configuration import settings
        from fastogram.session.drivers import DatabaseDriver, array_driver, unsign_id

        cfg = settings()
        raw_cookie = self._read_cookie(cfg.cookie)
        sid = unsign_id(raw_cookie) if raw_cookie else None
        if sid is None:
            return {}
        driver = DatabaseDriver(cfg.table) if cfg.driver == "database" else array_driver()
        record = await driver.load(sid, cfg.lifetime * 60)
        return dict(record.data) if record is not None else {}

    async def assert_authenticated(self) -> None:
        from fastogram.auth.guard import session_key

        data = await self._current_session()
        assert data.get(session_key()) is not None, "Expected the test client to be authenticated, but it is a guest."

    async def assert_authenticated_as(self, user: Any) -> None:
        from fastogram.auth.guard import session_key

        data = await self._current_session()
        actual = data.get(session_key())
        assert actual == user.id, f"Expected to be authenticated as user [{user.id}], session has [{actual!r}]."

    async def assert_guest(self) -> None:
        from fastogram.auth.guard import session_key

        data = await self._current_session()
        assert data.get(session_key()) is None, f"Expected a guest, but session has login id [{data.get(session_key())!r}]."

    # ------------------------------------------------------------ internals

    async def _apply_pending_session(self) -> dict[str, str]:
        """`acting_as`/`with_session`: write into the session store, and return `{cookie_name:
        value}` to send on the next request only (never written straight into the jar -- see
        `_read_cookie`'s docstring for why that misfires for a host like `testserver`).
        """
        if self._state.acting_as_user is None and not self._state.session_patch:
            return {}
        from fastogram.session.configuration import settings
        from fastogram.session.drivers import DatabaseDriver, SessionRecord, array_driver, sign_id, unsign_id
        from fastogram.session.store import Session, new_id

        cfg = settings()
        raw_cookie = self._read_cookie(cfg.cookie)
        driver = DatabaseDriver(cfg.table) if cfg.driver == "database" else array_driver()
        sid = unsign_id(raw_cookie) if raw_cookie else None
        existing: dict[str, Any] = {}
        if sid is not None:
            record = await driver.load(sid, cfg.lifetime * 60)
            if record is not None:
                existing = record.data
        else:
            sid = new_id()
        session = Session(sid, dict(existing), is_new=False)
        if self._state.session_patch:
            session.put(self._state.session_patch)
        if self._state.acting_as_user is not None:
            from fastogram.auth.guard import password_hash_key, session_key

            user = self._state.acting_as_user
            session.put(session_key(), user.id)
            session.put(password_hash_key(), getattr(user, "password", None))
        await driver.save(SessionRecord(session.id(), session.data, int(time.time())))
        return {cfg.cookie: sign_id(session.id())}

    async def _request(self, method: str, url: str, **kwargs: Any) -> TestResponse:
        session_cookies = await self._apply_pending_session()

        headers: dict[str, str] = dict(kwargs.pop("headers", None) or {})
        headers.update(self._state.headers)
        if self._state.referer:
            headers.setdefault("Referer", self._absolute_url(self._state.referer))
        if self._state.inertia:
            version = self._state.inertia_version
            if version is None:
                version = await self._asset_version()
            headers.setdefault("X-Inertia", "true")
            headers.setdefault("X-Requested-With", "XMLHttpRequest")
            headers.setdefault("X-Inertia-Version", version)

        extra_scope_state: dict[str, Any] = {}
        if self._state.force_csrf:
            extra_scope_state["fastogram.force_csrf"] = True
        if self._state.without_middleware:
            extra_scope_state["fastogram.without_middleware"] = self._state.without_middleware

        kwargs["headers"] = headers
        kwargs.setdefault("follow_redirects", self._state.follow)
        cookies = {**self._state.extra_cookies, **session_cookies}
        if cookies:
            kwargs["cookies"] = cookies
        response = await self._send(method, url, extra_scope_state, **kwargs)
        return response

    async def _replay(self, method: str, url: str, headers: dict[str, str]) -> TestResponse:
        """Repeat a previous request's URL/method with different headers (partial reloads)."""
        session_cookies = await self._apply_pending_session()
        extra_scope_state: dict[str, Any] = {}
        if self._state.force_csrf:
            extra_scope_state["fastogram.force_csrf"] = True
        if self._state.without_middleware:
            extra_scope_state["fastogram.without_middleware"] = self._state.without_middleware
        cookies = {**self._state.extra_cookies, **session_cookies}
        kwargs: dict[str, Any] = {"headers": headers}
        if cookies:
            kwargs["cookies"] = cookies
        return await self._send(method, url, extra_scope_state, **kwargs)

    async def _send(self, method: str, url: str, extra_scope_state: dict[str, Any], **kwargs: Any) -> TestResponse:
        from fastogram.foundation.application import current_application

        state_token = _pending_scope_state.set(extra_scope_state)
        capture: dict[str, Any] = {}
        capture_token = _pending_capture.set(capture)
        application = current_application()
        previous_raise = application.raise_exceptions if application is not None else None
        if application is not None and self._state.raise_exceptions:
            application.raise_exceptions = True
        try:
            httpx_response = await self._http.request(method, url, **kwargs)
        finally:
            _pending_scope_state.reset(state_token)
            _pending_capture.reset(capture_token)
            if application is not None and previous_raise is not None:
                application.raise_exceptions = previous_raise
        return TestResponse(httpx_response, self, capture)

    def _absolute_url(self, url: str) -> str:
        """`from_url("/posts/create")` sets the `Referer` header; `back()`'s same-origin check
        (`fastogram.http.responses.resolve_previous_url`) compares scheme+netloc against the
        current request, so a bare path would never match. Resolve it against `base_url`."""
        if "://" in url:
            return url
        return str(self._http.base_url.join(url))

    async def _asset_version(self) -> str:
        try:
            from fastogram.inertia.vite import manifest_hash

            return manifest_hash()
        except Exception:
            return ""

    async def aclose(self) -> None:
        await self._http.aclose()
