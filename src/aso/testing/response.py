"""`TestResponse` (T-56): fluent assertions over one HTTP response made through `TestClient`."""

from __future__ import annotations

import html
import json
import re
from typing import TYPE_CHECKING, Any

from aso.testing.inertia_assert import AssertableInertia

if TYPE_CHECKING:
    from aso.testing.client import TestClient

__all__ = ["TestResponse"]

_MISSING = object()
_PAGE_RE = re.compile(r'<script data-page="app" type="application/json">(.*?)</script>', re.DOTALL)


def _dig(data: Any, key: str, default: Any = _MISSING) -> Any:
    node = data
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return node


def _json_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and _json_subset(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        return all(_json_subset(e, a) for e, a in zip(expected, actual, strict=True))
    return expected == actual


class TestResponse:
    """Wraps one `httpx2.Response` plus the session/exception snapshot the plugin captured
    while the request was still inside the ASGI stack (T-56 "How it works")."""

    __test__ = False  # not a pytest test class, despite the name (T-56's public API name)

    def __init__(self, response: Any, client: TestClient, capture: dict[str, Any] | None = None) -> None:
        self._response = response
        self._client = client
        self._capture = capture or {}
        self.__page_cache: Any = _MISSING

    # ------------------------------------------------------------ raw access

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> Any:
        return self._response.headers

    @property
    def cookies(self) -> Any:
        return self._response.cookies

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def content(self) -> bytes:
        return self._response.content

    def json(self) -> Any:
        return self._response.json()

    # ------------------------------------------------------------ session snapshot

    def _session_data(self) -> dict[str, Any]:
        return self._capture.get("session") or {}

    def _reported_exception(self) -> BaseException | None:
        return self._capture.get("exception")

    def _fail(self, message: str) -> str:
        exc = self._reported_exception()
        extra = ""
        if exc is not None:
            extra = f"\n\nThe handler reported: {type(exc).__name__}: {exc}"
        body_preview = self.text[:2000]
        return f"{message}{extra}\n\nResponse [{self.status_code}]: {body_preview}"

    # ------------------------------------------------------------ status

    def assert_status(self, status: int) -> TestResponse:
        assert self.status_code == status, self._fail(f"Expected status [{status}], got [{self.status_code}].")
        return self

    def assert_ok(self) -> TestResponse:
        return self.assert_status(200)

    def assert_created(self) -> TestResponse:
        return self.assert_status(201)

    def assert_no_content(self) -> TestResponse:
        return self.assert_status(204)

    def assert_successful(self) -> TestResponse:
        assert 200 <= self.status_code < 300, self._fail(f"Expected a successful status, got [{self.status_code}].")
        return self

    def assert_unauthorized(self) -> TestResponse:
        return self.assert_status(401)

    def assert_forbidden(self) -> TestResponse:
        return self.assert_status(403)

    def assert_not_found(self) -> TestResponse:
        return self.assert_status(404)

    def assert_conflict(self) -> TestResponse:
        return self.assert_status(409)

    def assert_unprocessable(self) -> TestResponse:
        return self.assert_status(422)

    def assert_too_many_requests(self) -> TestResponse:
        return self.assert_status(429)

    def assert_server_error(self) -> TestResponse:
        return self.assert_status(500)

    def assert_redirect(self, url: str | None = None) -> TestResponse:
        assert 300 <= self.status_code < 400, self._fail(f"Expected a redirect, got [{self.status_code}].")
        if url is not None:
            location = self._response.headers.get("location", "")
            assert location == url or location.endswith(url), (
                self._fail(f"Expected redirect to [{url}], got [{location}].")
            )
        return self

    def assert_redirect_to_route(self, name: str, *params: Any) -> TestResponse:
        from aso.routing import route

        expected = route(name, params[0] if len(params) == 1 else (list(params) or None))
        return self.assert_redirect(expected)

    # ------------------------------------------------------------ session

    def assert_session_has(self, key: str, value: Any = _MISSING) -> TestResponse:
        data = self._session_data()
        actual = _dig(data, key)
        assert actual is not _MISSING, self._fail(f"Session is missing key [{key}]. Session: {data!r}.")
        if value is not _MISSING:
            assert actual == value, self._fail(f"Session[{key}] = {actual!r}, expected {value!r}.")
        return self

    def assert_session_missing(self, key: str) -> TestResponse:
        data = self._session_data()
        actual = _dig(data, key)
        assert actual is _MISSING, self._fail(f"Session unexpectedly has key [{key}] = {actual!r}.")
        return self

    def _error_bags(self) -> dict[str, dict[str, list[str]]]:
        data = self._session_data()
        bags = data.get("errors") or {}
        return bags if isinstance(bags, dict) else {}

    def assert_session_has_errors(
        self,
        errors: list[str] | dict[str, str],
        bag: str = "default",
        partial: bool = False,
    ) -> TestResponse:
        fields = self._error_bags().get(bag, {})
        if isinstance(errors, dict):
            for field, expected_message in errors.items():
                messages = fields.get(field)
                assert messages, self._fail(f"Session has no error for [{field}] in bag [{bag}]. Errors: {fields!r}.")
                first = messages[0]
                if partial:
                    assert expected_message in first, self._fail(
                        f"Error for [{field}] = {first!r} does not contain {expected_message!r}."
                    )
                else:
                    assert first == expected_message, self._fail(
                        f"Error for [{field}] = {first!r}, expected {expected_message!r}."
                    )
        else:
            for field in errors:
                assert field in fields, self._fail(
                    f"Session has no error for [{field}] in bag [{bag}]. Errors: {fields!r}."
                )
        return self

    def assert_session_has_no_errors(self) -> TestResponse:
        bags = self._error_bags()
        assert not any(bags.values()), self._fail(f"Session unexpectedly has validation errors: {bags!r}.")
        return self

    # ------------------------------------------------------------ headers / cookies / content

    def assert_header(self, name: str, value: Any = _MISSING) -> TestResponse:
        actual = self._response.headers.get(name)
        assert actual is not None, self._fail(f"Response is missing header [{name}]. Headers: {dict(self._response.headers)!r}.")
        if value is not _MISSING:
            assert actual == value, self._fail(f"Header [{name}] = {actual!r}, expected {value!r}.")
        return self

    def assert_cookie(self, name: str, value: Any = _MISSING) -> TestResponse:
        actual = self._response.cookies.get(name)
        assert actual is not None, self._fail(f"Response is missing cookie [{name}].")
        if value is not _MISSING:
            assert actual == value, self._fail(f"Cookie [{name}] = {actual!r}, expected {value!r}.")
        return self

    def assert_cookie_missing(self, name: str) -> TestResponse:
        actual = self._response.cookies.get(name)
        assert actual is None, self._fail(f"Response unexpectedly has cookie [{name}] = {actual!r}.")
        return self

    def assert_see(self, text: str, escape: bool = True) -> TestResponse:
        needle = html.escape(text) if escape else text
        assert needle in self._response.text, self._fail(f"Did not find {needle!r} in the response body.")
        return self

    # ------------------------------------------------------------ JSON

    def assert_json(self, data: dict[str, Any]) -> TestResponse:
        body = self.json()
        assert _json_subset(data, body), self._fail(f"JSON body does not contain {data!r}. Body: {body!r}.")
        return self

    def assert_exact_json(self, data: Any) -> TestResponse:
        body = self.json()
        assert body == data, self._fail(f"JSON body {body!r} != expected {data!r}.")
        return self

    def assert_json_path(self, path: str, value: Any) -> TestResponse:
        body = self.json()
        actual = _dig(body, path)
        assert actual is not _MISSING, self._fail(f"JSON path [{path}] does not exist. Body: {body!r}.")
        assert actual == value, self._fail(f"JSON path [{path}] = {actual!r}, expected {value!r}.")
        return self

    def assert_json_count(self, count: int, key: str | None = None) -> TestResponse:
        body = self.json()
        target = body if key is None else _dig(body, key)
        assert target is not _MISSING, self._fail(f"JSON path [{key}] does not exist.")
        assert len(target) == count, self._fail(f"JSON path [{key or '<root>'}] has {len(target)} item(s), expected {count}.")
        return self

    def assert_json_validation_errors(self, fields: list[str] | dict[str, str]) -> TestResponse:
        body = self.json()
        errors = body.get("errors") or {}
        if isinstance(fields, dict):
            for field, expected in fields.items():
                messages = errors.get(field)
                assert messages, self._fail(f"JSON response has no validation error for [{field}]. Errors: {errors!r}.")
                first = messages[0] if isinstance(messages, list) else messages
                assert first == expected, self._fail(f"Error for [{field}] = {first!r}, expected {expected!r}.")
        else:
            for field in fields:
                assert field in errors, self._fail(
                    f"JSON response has no validation error for [{field}]. Errors: {errors!r}."
                )
        return self

    # ------------------------------------------------------------ Inertia

    def _page(self) -> dict[str, Any] | None:
        if self.__page_cache is not _MISSING:
            return self.__page_cache
        content_type = self._response.headers.get("content-type", "")
        if self._response.headers.get("x-inertia") == "true" or "application/json" in content_type:
            try:
                page = self._response.json()
            except ValueError:
                page = None
        else:
            match = _PAGE_RE.search(self._response.text)
            page = json.loads(match.group(1)) if match else None
        self.__page_cache = page
        return page

    def assert_inertia(self, callback: Any) -> TestResponse:
        page = self._page()
        assert page is not None, self._fail(
            "Expected an Inertia response (JSON visit or HTML first visit with a `data-page` "
            "script tag), but could not parse one from this response."
        )
        callback(AssertableInertia(page))
        return self

    def assert_inertia_flash(self, key: str, value: Any = _MISSING) -> TestResponse:
        data = self._session_data()
        flash_state = data.get("_flash") or {"old": [], "new": []}
        visible = {k for k in (*flash_state.get("old", []), *flash_state.get("new", [])) if not k.startswith("_") and k != "errors"}
        assert key in visible, self._fail(f"The next page will not receive flash key [{key}]. Flash: {sorted(visible)}.")
        if value is not _MISSING:
            actual = data.get(key)
            assert actual == value, self._fail(f"Flash[{key}] = {actual!r}, expected {value!r}.")
        return self

    def inertia_props(self, path: str | None = None) -> Any:
        page = self._page()
        props = page.get("props", {}) if page else {}
        if path is None:
            return props
        value = _dig(props, path)
        return None if value is _MISSING else value

    async def reload_only(self, *props: str) -> TestResponse:
        return await self._partial_reload(only=props)

    async def reload_except(self, *props: str) -> TestResponse:
        return await self._partial_reload(except_=props)

    async def load_deferred_props(self, group: str | None = None) -> TestResponse:
        page = self._page()
        assert page is not None, self._fail("Expected an Inertia response with deferred props.")
        deferred: dict[str, list[str]] = page.get("deferredProps") or {}
        if group is not None:
            props = deferred.get(group, [])
        else:
            props = [name for names in deferred.values() for name in names]
        return await self._partial_reload(only=props)

    async def _partial_reload(self, only: Any = None, except_: Any = None) -> TestResponse:
        page = self._page()
        assert page is not None, self._fail("Cannot reload: this is not an Inertia response.")
        component = page["component"]
        request = self._response.request
        headers = {
            "X-Inertia": "true",
            "X-Requested-With": "XMLHttpRequest",
            "X-Inertia-Version": request.headers.get("x-inertia-version", ""),
            "X-Inertia-Partial-Component": component,
        }
        if only:
            headers["X-Inertia-Partial-Data"] = ",".join(only)
        if except_:
            headers["X-Inertia-Partial-Except"] = ",".join(except_)
        url = str(request.url)
        return await self._client._replay(request.method, url, headers)

    # ------------------------------------------------------------ dunder

    def __repr__(self) -> str:
        return f"<TestResponse [{self.status_code}]>"
