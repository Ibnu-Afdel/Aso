"""S-1 spike: our own Inertia v3 server protocol + Route facade + session flash, end to end.

Throwaway. Run: uv run uvicorn app:app --port 8765  (from spikes/s1, after `npm run build`)
"""

from __future__ import annotations

import contextvars
import hashlib
import hmac
import inspect
import json
import secrets
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "s2"))
sys.path.insert(0, str(HERE.parent / "s3"))
from db import DB, Model, configure  # noqa: E402
from messages import validate as validate_messages  # noqa: E402

# ----------------------------------------------------------------- request context

_ctx: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("fg_ctx")


def ctx() -> dict[str, Any]:
    return _ctx.get()


# ----------------------------------------------------------------- session (array driver)

_STORE: dict[str, dict[str, Any]] = {}


class Session:
    def __init__(self, id: str, data: dict[str, Any]):
        self.id, self.data = id, data
        self.data.setdefault("_flash", {"old": [], "new": []})
        self.data.setdefault("_token", secrets.token_urlsafe(30))

    def get(self, k, d=None):
        return self.data.get(k, d)

    def put(self, k, v):
        self.data[k] = v

    def forget(self, k):
        self.data.pop(k, None)

    def flash(self, k, v):
        self.put(k, v)
        f = self.data["_flash"]
        if k not in f["new"]:
            f["new"].append(k)
        if k in f["old"]:
            f["old"].remove(k)

    def reflash(self):
        f = self.data["_flash"]
        f["new"] = list(dict.fromkeys(f["new"] + f["old"]))
        f["old"] = []

    def age_flash(self):
        f = self.data["_flash"]
        for k in f["old"]:
            self.forget(k)
        f["old"], f["new"] = f["new"], []

    def token(self) -> str:
        return self.data["_token"]


def session() -> Session:
    return ctx()["session"]


def _cookies(scope) -> dict[str, str]:
    raw = dict(scope["headers"]).get(b"cookie", b"").decode()
    c = SimpleCookie()
    c.load(raw)
    return {k: v.value for k, v in c.items()}


def _header(scope, name: str) -> str | None:
    v = dict(scope["headers"]).get(name.lower().encode())
    return v.decode() if v is not None else None


def _add_cookie(message, name, value, http_only=True):
    flags = "Path=/; SameSite=lax" + ("; HttpOnly" if http_only else "")
    message.setdefault("headers", [])
    message["headers"] = list(message["headers"]) + [(b"set-cookie", f"{name}={value}; {flags}".encode())]


# ----------------------------------------------------------------- pure ASGI middleware


class RequestContext:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = _ctx.set({"shared": {}, "request": Request(scope)})
        try:
            await self.app(scope, receive, send)
        finally:
            _ctx.reset(token)


class DatabaseScope:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async with DB.scope(fresh=True):
            await self.app(scope, receive, send)


class StartSession:
    COOKIE = "s1-session"

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        sid = _cookies(scope).get(self.COOKIE)
        if not sid or sid not in _STORE:
            sid = secrets.token_urlsafe(30)
        s = Session(sid, json.loads(json.dumps(_STORE.get(sid, {}))))
        ctx()["session"] = s
        prefetch = _header(scope, "purpose") == "prefetch"

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status = message["status"]
                if scope["method"] == "GET" and status == 200 and not prefetch and not _header(scope, "x-inertia-partial-data"):
                    qs = scope.get("query_string", b"").decode()
                    s.put("_previous_url", scope["path"] + (f"?{qs}" if qs else ""))
                if not prefetch:
                    s.age_flash()
                _STORE[s.id] = s.data
                _add_cookie(message, self.COOKIE, s.id)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class TokenMismatch(Exception):
    pass


class PreventRequestForgery:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            # spike: deliberately skip the Sec-Fetch-Site shortcut to prove the token path works
            supplied = _header(scope, "x-xsrf-token") or _header(scope, "x-csrf-token") or ""
            if not hmac.compare_digest(supplied, session().token()):
                resp = JSONResponse({"message": "CSRF token mismatch."}, status_code=419)
                return await resp(scope, receive, self._sender(send))
        await self.app(scope, receive, self._sender(send))

    def _sender(self, send):
        async def wrapper(message):
            if message["type"] == "http.response.start":
                _add_cookie(message, "XSRF-TOKEN", session().token(), http_only=False)
            await send(message)
        return wrapper


class InertiaMiddleware:
    root_view = "app.html"

    def __init__(self, app):
        self.app = app

    async def version(self) -> str:
        override = HERE / "version.txt"
        if override.exists():
            return override.read_text().strip()
        manifest = HERE / "public/build/manifest.json"
        return hashlib.md5(manifest.read_bytes()).hexdigest() if manifest.exists() else ""

    async def share(self, request) -> dict:
        return {"app_name": "S1"}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        ctx()["inertia_mw"] = self
        is_inertia = _header(scope, "x-inertia") == "true"
        if is_inertia and scope["method"] == "GET" and _header(scope, "x-inertia-version") != await self.version():
            session().reflash()
            host = _header(scope, "host")
            qs = scope.get("query_string", b"").decode()
            url = f"{scope['scheme']}://{host}{scope['path']}" + (f"?{qs}" if qs else "")
            resp = Response(status_code=409, headers={"X-Inertia-Location": url,
                                                      "X-Inertia-Version": await self.version()})
            return await resp(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if is_inertia and message["status"] == 302 and scope["method"] in ("PUT", "PATCH", "DELETE"):
                    message["status"] = 303
                headers.append((b"vary", b"X-Inertia"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ----------------------------------------------------------------- inertia()


class Deferred:
    def __init__(self, fn, group="default"):
        self.fn, self.group = fn, group


def defer(fn, group="default"):
    return Deferred(fn, group)


async def _resolve(value):
    if callable(value):
        value = value()
    if inspect.isawaitable(value):
        value = await value
    return value


def _jsonable(v):
    if isinstance(v, Model):
        return {c.key: getattr(v, c.key) for c in v.__table__.columns}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


jinja = Environment(loader=FileSystemLoader(HERE / "views"), autoescape=True)


def vite(entry: str) -> Markup:
    manifest = json.loads((HERE / "public/build/manifest.json").read_text())
    chunk = manifest[entry]
    tags = [f'<script type="module" src="/build/{chunk["file"]}"></script>']
    tags += [f'<link rel="stylesheet" href="/build/{css}">' for css in chunk.get("css", [])]
    return Markup("\n".join(tags))


class InertiaResponse(Response):
    def __init__(self, component: str, props: dict | None = None):
        super().__init__()
        self.component, self.props = component, props or {}

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive)
        mw: InertiaMiddleware = ctx()["inertia_mw"]
        partial = (request.headers.get("x-inertia") == "true"
                   and request.headers.get("x-inertia-partial-component") == self.component)
        only = [k for k in (request.headers.get("x-inertia-partial-data") or "").split(",") if k]
        props = {**await mw.share(request), **ctx()["shared"], **self.props}
        page_props: dict[str, Any] = {}
        deferred: dict[str, list[str]] = {}
        for key, value in props.items():          # one after another: one AsyncSession
            if partial and only and key not in only:
                continue
            if isinstance(value, Deferred):
                if not partial:
                    deferred.setdefault(value.group, []).append(key)
                    continue
                value = value.fn
            page_props[key] = _jsonable(await _resolve(value))
        s = session()
        errors = s.get("errors") or {}
        page_props["errors"] = {k: v[0] for k, v in errors.get("default", {}).items()}
        page: dict[str, Any] = {
            "component": self.component,
            "props": page_props,
            "url": request.url.path + (f"?{request.url.query}" if request.url.query else ""),
            "version": await mw.version(),
        }
        if deferred:
            page["deferredProps"] = deferred
        if request.headers.get("purpose") != "prefetch":
            f = s.data["_flash"]
            visible = [k for k in f["old"] + f["new"] if not k.startswith("_") and k != "errors"]
            flash = {k: s.get(k) for k in visible}
            for k in list(f["new"]):
                if k in visible:
                    f["new"].remove(k)
                    f["old"].append(k)
            if flash:
                page["flash"] = flash
        if request.headers.get("x-inertia") == "true":
            resp: Response = JSONResponse(page, headers={"X-Inertia": "true"})
        else:
            data = json.dumps(page).replace("/", "\\/")
            app_html = Markup(f'<script data-page="app" type="application/json">{data}</script><div id="app"></div>')
            html = jinja.get_template(mw.root_view).render(page=page, inertia_app=app_html, vite=vite)
            resp = HTMLResponse(html)
        await resp(scope, receive, send)


def inertia(component: str, props: dict | None = None) -> InertiaResponse:
    return InertiaResponse(component, props)


# ----------------------------------------------------------------- redirects


def back() -> RedirectResponse:
    request: Request = ctx()["request"]
    ref = request.headers.get("referer")
    if ref:
        p = urlparse(ref)
        if p.netloc == request.url.netloc:
            return RedirectResponse(p.path + (f"?{p.query}" if p.query else ""), status_code=302)
    return RedirectResponse(session().get("_previous_url") or "/", status_code=302)


class Redirect(RedirectResponse):
    def with_flash(self, k, v):
        session().flash(k, v)
        return self


def redirect(url: str) -> Redirect:
    return Redirect(url, status_code=302)


# ----------------------------------------------------------------- FormRequest


class ValidationException(Exception):
    def __init__(self, errors, bag="default"):
        self.errors, self.bag = errors, bag


class FormRequest(BaseModel):
    @classmethod
    async def resolve(cls, request: Request):
        ctype = request.headers.get("content-type", "")
        data = await request.json() if "json" in ctype else dict(await request.form())
        data = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in data.items()}
        obj, errors = validate_messages(cls, data)
        if errors:
            raise ValidationException(errors, request.headers.get("x-inertia-error-bag") or "default")
        return obj

    def validated(self) -> dict:
        return self.model_dump()


# ----------------------------------------------------------------- Route facade


class _Def:
    def __init__(self, methods, path, action):
        self.methods, self.path, self.action, self._name = methods, path, action, None

    def name(self, n):
        self._name = n
        return self


class Route:
    defs: list[_Def] = []

    @classmethod
    def get(cls, path, action):
        d = _Def(["GET"], path, action)
        cls.defs.append(d)
        return d

    @classmethod
    def post(cls, path, action):
        d = _Def(["POST"], path, action)
        cls.defs.append(d)
        return d

    @classmethod
    def compile(cls, app: FastAPI):
        for d in cls.defs:
            app.add_api_route(d.path, _endpoint(d.action), methods=d.methods, name=d._name,
                              include_in_schema=False)


def route(name: str) -> str:
    return next(d.path for d in Route.defs if d._name == name)


def _endpoint(action):
    controller, method_name = action
    method = getattr(controller, method_name)
    sig = inspect.signature(method)
    hints = {k: v for k, v in getattr(method, "__annotations__", {}).items()}
    params = []
    for p in list(sig.parameters.values())[1:]:
        ann = hints.get(p.name, p.annotation)
        if isinstance(ann, str):
            ann = eval(ann, sys.modules[method.__module__].__dict__)
        if isinstance(ann, type) and issubclass(ann, FormRequest):
            params.append(p.replace(annotation=ann, default=Depends(ann.resolve), kind=inspect.Parameter.KEYWORD_ONLY))
        else:
            params.append(p.replace(annotation=ann, kind=inspect.Parameter.KEYWORD_ONLY))

    async def endpoint(request: Request, **kwargs):
        ctx()["request"] = request
        result = await method(controller(), **kwargs)
        if isinstance(result, (dict, list)):
            return JSONResponse(_jsonable(result))
        return result

    endpoint.__signature__ = inspect.Signature(
        [inspect.Parameter("request", inspect.Parameter.KEYWORD_ONLY, annotation=Request)] + params
    )
    return endpoint


# ----------------------------------------------------------------- the app


class Post(Model):
    __tablename__ = "posts"
    title: Mapped[str] = mapped_column(String(100))


class StorePostRequest(FormRequest):
    title: str = Field(min_length=3, max_length=100)


class Controller:
    pass


class PostController(Controller):
    async def index(self):
        return inertia("posts/index", {"posts": defer(lambda: Post.all())})

    async def create(self):
        return inertia("posts/create")

    async def store(self, form: StorePostRequest):
        await Post.create(**form.validated())
        return redirect(route("posts.index")).with_flash("success", "Post created.")

    async def stats(self):
        return {"count": len(await Post.all())}


Route.get("/posts", [PostController, "index"]).name("posts.index")
Route.get("/posts/create", [PostController, "create"]).name("posts.create")
Route.post("/posts", [PostController, "store"]).name("posts.store")
Route.get("/stats", [PostController, "stats"]).name("stats")


def create_app() -> FastAPI:
    engine = create_async_engine("sqlite+aiosqlite:///" + str(HERE / "s1.sqlite"))
    configure(engine)
    app = FastAPI()

    @app.on_event("startup")
    async def _migrate():
        async with engine.begin() as c:
            await c.run_sync(Model.metadata.drop_all)
            await c.run_sync(Model.metadata.create_all)

    @app.exception_handler(ValidationException)
    async def _validation(request: Request, exc: ValidationException):
        s = session()
        s.flash("errors", {exc.bag: exc.errors})
        return back()

    Route.compile(app)
    from fastapi.staticfiles import StaticFiles
    app.mount("/build", StaticFiles(directory=HERE / "public/build"), name="build")
    # outermost last
    app.add_middleware(InertiaMiddleware)
    app.add_middleware(PreventRequestForgery)
    app.add_middleware(StartSession)
    app.add_middleware(DatabaseScope)
    app.add_middleware(RequestContext)
    return app


app = create_app()
