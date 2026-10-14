"""`fastogram.http.Request` (T-14).

Body cache shared through the ASGI scope + `receive_replay()`, so a middleware, a `FormRequest`
and the controller can all read the body. Bodies over `config("app.max_buffered_body")` (default
10 MB) raise `RequestBodyTooLarge` -- stream them in the controller instead.
"""

from __future__ import annotations

import fnmatch
import json
from typing import Any

from starlette.requests import Request as StarletteRequest
from starlette.types import Message, Receive

from fastogram.exceptions.types import RequestBodyTooLarge

_BODY_KEY = "fastogram.body"
_INPUT_KEY = "fastogram.input"
_MISSING = object()

DEFAULT_MAX_BUFFERED_BODY = 10 * 1024 * 1024


def _max_buffered_body() -> int:
    from fastogram.config import config

    return int(config("app.max_buffered_body", DEFAULT_MAX_BUFFERED_BODY))


class Request(StarletteRequest):
    """A Starlette request whose body is cached in the scope, so every Request object built for
    the same ASGI scope (middleware, FastAPI's own, ours) can read the body again."""

    # ------------------------------------------------------------ body cache

    async def body(self) -> bytes:
        cached = self.scope.get(_BODY_KEY)
        if cached is not None:
            return cached
        limit = _max_buffered_body()
        content_length = self.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    raise RequestBodyTooLarge(limit)
            except ValueError:
                pass
        body = await super().body()
        if len(body) > limit:
            raise RequestBodyTooLarge(limit)
        self.scope[_BODY_KEY] = body
        return body

    def receive_replay(self, receive: Receive) -> Receive:
        """A `receive` that replays the cached body once it has been read by anyone."""
        scope = self.scope
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            cached = scope.get(_BODY_KEY)
            if cached is not None and not replayed:
                replayed = True
                return {"type": "http.request", "body": cached, "more_body": False}
            if cached is not None and replayed:
                # body already delivered; wait for disconnect like Starlette does
                return await receive()
            return await receive()

        return replay

    # ------------------------------------------------------------ input (async: body I/O)

    async def _collect_all(self) -> dict[str, Any]:
        cached = self.scope.get(_INPUT_KEY)
        if cached is not None:
            return cached
        data: dict[str, Any] = dict(self.query_params)
        if self.method not in ("GET", "HEAD"):
            content_type = self.headers.get("content-type", "")
            if "json" in content_type:
                body = await self.body()
                if body:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        data.update(parsed)
            elif "form" in content_type:
                form = await self.form()
                flat: dict[str, Any] = {}
                for key in form.keys():
                    values = form.getlist(key)
                    flat[key] = values if len(values) > 1 else values[0]
                data.update(expand_bracket_keys(flat))
        self.scope[_INPUT_KEY] = data
        return data

    async def all(self) -> dict[str, Any]:
        return await self._collect_all()

    async def input(self, key: str | None = None, default: Any = None) -> Any:
        data = await self._collect_all()
        if key is None:
            return data
        value = _dig(data, key, _MISSING)
        return default if value is _MISSING else value

    async def has(self, key: str) -> bool:
        data = await self._collect_all()
        return _dig(data, key, _MISSING) is not _MISSING

    async def boolean(self, key: str, default: bool = False) -> bool:
        value = await self.input(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "on", "yes"}
        return bool(value)

    async def only(self, *keys: str) -> dict[str, Any]:
        data = await self._collect_all()
        return {k: data[k] for k in keys if k in data}

    async def except_(self, *keys: str) -> dict[str, Any]:
        data = await self._collect_all()
        return {k: v for k, v in data.items() if k not in keys}

    async def file(self, key: str) -> Any:
        """The uploaded file (Starlette's `UploadFile`: `.filename`, `.content_type`, `.size`), or
        `None`. Storing it on disk is covered by `fastogram.storage` (T-43)."""
        from starlette.datastructures import UploadFile

        form = await self.form()
        value = form.get(key)
        return value if isinstance(value, UploadFile) else None

    # ------------------------------------------------------------ inspection (sync)

    def query(self, key: str | None = None, default: Any = None) -> Any:
        """Query-string reads are synchronous (no body I/O, T-14): `request.query("page", default=1)`."""
        if key is None:
            return dict(self.query_params)
        return self.query_params.get(key, default)

    def header(self, name: str, default: Any = None) -> Any:
        return self.headers.get(name, default)

    def cookie(self, name: str, default: Any = None) -> Any:
        return self.cookies.get(name, default)

    def path(self) -> str:
        return self.url.path

    def full_url(self) -> str:
        return str(self.url)

    def is_(self, *patterns: str) -> bool:
        path = self.url.path.lstrip("/")
        return any(fnmatch.fnmatch(path, pattern.lstrip("/")) for pattern in patterns)

    def route_is(self, *patterns: str) -> bool:
        from fastogram import context

        ctx = context.current()
        name = getattr(ctx.route, "route_name", None) if ctx is not None else None
        if not name:
            return False
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    def expects_json(self) -> bool:
        from fastogram import context

        ctx = context.current()
        if ctx is not None and ctx.group == "api":
            return True
        if self.inertia():
            return False
        accept = self.headers.get("accept", "")
        return "application/json" in accept or "+json" in accept

    def inertia(self) -> bool:
        return self.headers.get("x-inertia") == "true"

    def client_ip(self) -> str | None:
        return self.client.host if self.client else None

    def old(self, key: str, default: Any = None) -> Any:
        from fastogram import context

        ctx = context.current()
        if ctx is None or ctx.session is None:
            return default
        stored = ctx.session.get("_old_input") or {}
        return stored.get(key, default)

    def route_params(self) -> dict[str, Any]:
        """Route parameters, including route-model-bound instances (T-10)."""
        from fastogram import context

        ctx = context.current()
        return ctx.route_params if ctx is not None else {}

    # ------------------------------------------------------------ session, auth

    def session(self) -> Any:
        from fastogram.session import session

        return session()

    def user(self) -> Any:
        try:
            from fastogram.auth import auth
        except ImportError:
            return None
        return auth().user()


def _dig(data: Any, key: str, default: Any) -> Any:
    node = data
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.lstrip("-").isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return default
    return node


# ---------------------------------------------------------------- bracket-key form input


def expand_bracket_keys(flat: dict[str, Any]) -> dict[str, Any]:
    """`{"lines[0][quantity]": "2", "tags[]": ["a", "b"]}` -> nested dicts/lists, as Inertia's
    `FormData` conversion produces them. Usable by `fastogram.validation` when collecting input."""
    root: dict[str, Any] = {}
    for raw_key, value in flat.items():
        _set(root, _tokenize(raw_key), value)
    return _listify(root)


def _tokenize(raw_key: str) -> list[str]:
    if "[" not in raw_key:
        return [raw_key]
    head, _, rest = raw_key.partition("[")
    tokens = [head]
    for part in rest.split("["):
        tokens.append(part[:-1] if part.endswith("]") else part)
    return tokens


def _set(node: dict[str, Any], tokens: list[str], value: Any) -> None:
    key = tokens[0]
    if len(tokens) == 1:
        node[key] = value
        return
    child = node.setdefault(key, {})
    if not isinstance(child, dict):
        child = {}
        node[key] = child
    next_token = tokens[1]
    if next_token == "":
        bucket = child.setdefault("__append__", [])
        if len(tokens) == 2:
            bucket.extend(value) if isinstance(value, list) else bucket.append(value)
        else:
            item: dict[str, Any] = {}
            bucket.append(item)
            _set(item, tokens[2:], value)
    else:
        _set(child, tokens[1:], value)


def _listify(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if "__append__" in node and len(node) == 1:
        return [_listify(v) for v in node["__append__"]]
    plain_keys = [k for k in node if k != "__append__"]
    if plain_keys and all(k.isdigit() for k in plain_keys):
        items = sorted(((int(k), node[k]) for k in plain_keys), key=lambda kv: kv[0])
        return [_listify(v) for _, v in items]
    return {k: _listify(v) for k, v in node.items() if k != "__append__"}
