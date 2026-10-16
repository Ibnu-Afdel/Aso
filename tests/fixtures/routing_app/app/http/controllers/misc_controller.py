"""Grab-bag controller for routing/HTTP feature tests that don't need their own controller."""

from __future__ import annotations

import uuid as _uuid

from aso.http import Controller, Request, Response, abort, abort_if, abort_unless, back, redirect
from aso.http import response as response_builder
from aso.routing import url

INNER_RAN = {"value": False}


class MiscController(Controller):
    # -- verbs / match / any -------------------------------------------------------------

    async def echo_method(self, request: Request):
        return {"method": request.method}

    async def search(self, request: Request):
        return {"q": request.query("q", default="")}

    async def ping(self):
        return {"ok": True}

    # -- route parameters -----------------------------------------------------------------

    async def user_post(self, user_id: int, post_id: int):
        return {"user_id": user_id, "post_id": post_id}

    async def archive(self, year: int | None = None):
        return {"year": year}

    async def order(self, id: int):
        return {"id": id}

    async def tag(self, name: str):
        return {"name": name}

    async def file_by_uuid(self, uuid: _uuid.UUID):
        return {"uuid": str(uuid)}

    async def doc(self, path: str):
        return {"path": path}

    # -- request inspection -----------------------------------------------------------------

    async def inspect(self, request: Request) -> Response:
        return response_builder().json(
            {
                "path": request.path(),
                "full_url": request.full_url(),
                "method": request.method,
                "header": request.header("X-Custom", "none"),
                "cookie": request.cookie("flavor", "none"),
                "query": request.query("q", default=None),
                "is_admin": request.is_("admin/*"),
                "route_is": request.route_is("misc.inspect"),
                "expects_json": request.expects_json(),
                "is_inertia": request.inertia(),
                "client_ip": request.client_ip(),
                "all": await request.all(),
                "input_title": await request.input("title", default="none"),
                "has_title": await request.has("title"),
                "boolean_flag": await request.boolean("flag"),
                "only": await request.only("title"),
                "except_": await request.except_("title"),
            }
        )

    async def echo_body(self, request: Request):
        return {"x": await request.input("x")}

    async def upload(self, request: Request):
        file = await request.file("avatar")
        if file is None:
            return {"file": None}
        return {"filename": file.filename, "content_type": file.content_type}

    # -- response() builder -----------------------------------------------------------------

    async def json_response(self):
        return response_builder().json({"ok": True}, status=201, headers={"X-Report-Id": "7"})

    async def no_content(self):
        return response_builder().no_content()

    async def download_action(self, request: Request):
        path = await request.input("path")
        name = await request.input("name")
        return response_builder().download(path, name)

    async def file_action(self, request: Request):
        path = await request.input("path")
        return response_builder().file(path)

    async def stream_action(self):
        async def lines():
            for i in range(3):
                yield f"line {i}\n"

        return response_builder().stream(lines(), media_type="text/plain")

    # -- abort --------------------------------------------------------------------------

    async def abort_action(self, request: Request):
        status = int(request.query("status", default="400"))
        abort(status, "nope")

    async def abort_if_action(self, request: Request):
        cond = (request.query("cond", default="false")) == "true"
        abort_if(cond, 418, "teapot")
        return {"ok": True}

    async def abort_unless_action(self, request: Request):
        cond = (request.query("cond", default="false")) == "true"
        abort_unless(cond, 418, "teapot")
        return {"ok": True}

    # -- redirects ------------------------------------------------------------------------

    async def redirect_to(self):
        return redirect().to("/misc/ping")

    async def redirect_named(self):
        return redirect().route("misc.ping")

    async def redirect_back(self):
        return back()

    async def set_intended(self):
        from aso.session import session

        session().put("url.intended", "/misc/ping")
        return {"ok": True}

    async def redirect_intended(self):
        return redirect().intended("/misc/default")

    async def redirect_away(self):
        return redirect().away("https://example.com/elsewhere")

    async def redirect_flash(self):
        return redirect().to("/misc/ping").with_flash("success", "done")

    async def redirect_flash_dict(self):
        return redirect().to("/misc/ping").with_flash({"success": "done", "highlight": 1})

    async def redirect_errors(self):
        return redirect().to("/misc/ping").with_errors({"email": "bad"})

    async def redirect_errors_bag(self):
        return redirect().to("/misc/ping").with_errors({"email": "bad"}, bag="invite")

    async def redirect_with_input(self, request: Request):
        await request.all()
        return redirect().to("/misc/ping").with_input()

    async def redirect_fragment(self):
        return redirect().to("/misc/ping").with_fragment("comments")

    async def redirect_cookie(self):
        return redirect().to("/misc/ping").cookie("appearance", "dark", minutes=60, http_only=False)

    async def redirect_without_cookie(self):
        return redirect().to("/misc/ping").without_cookie("appearance")

    # -- url() helpers ----------------------------------------------------------------------

    async def url_action(self):
        return {
            "plain": url("/misc/ping"),
            "current": url().current(),
            "previous": url().previous(),
        }

    # -- middleware demo endpoints ----------------------------------------------------------

    async def noop(self):
        return {"ok": True}

    async def mark_ran(self):
        INNER_RAN["value"] = True
        return {"inner": True}

    async def secure(self):
        return {"secure": True}

    async def secret(self, id: int):
        return {"id": id}
