from fastapi import APIRouter

from fastogram.routing import Route

from app.http.controllers.comment_controller import CommentController
from app.http.controllers.convert_controller import ConvertController
from app.http.controllers.fallback_controller import FallbackController
from app.http.controllers.gated_controller import GatedController
from app.http.controllers.group_controller import GroupController
from app.http.controllers.misc_controller import MiscController
from app.http.controllers.ping_invokable import PingInvokable
from app.http.controllers.post_controller import PostController

# -- resources ------------------------------------------------------------------------------

Route.resource("posts", PostController)
Route.get("/posts-by-slug/{post:slug}", [PostController, "show_by_slug"]).name("posts.show_by_slug")
Route.resource("posts.comments", CommentController)

# -- verbs / match / any ---------------------------------------------------------------------

Route.get("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.get")
Route.post("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.post")
Route.put("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.put")
Route.patch("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.patch")
Route.delete("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.delete")
Route.options("/misc/echo", [MiscController, "echo_method"]).name("misc.echo.options")
Route.match(["get", "post"], "/misc/search", [MiscController, "search"]).name("misc.search")
Route.any("/misc/any", [MiscController, "ping"]).name("misc.any")

Route.redirect("/misc/home-old", "/misc/ping").name("misc.redirect_default")
Route.redirect("/misc/old-blog", "/misc/ping", status=301).name("misc.redirect_301")
Route.permanent_redirect("/misc/legacy", "/misc/ping").name("misc.permanent_redirect")
Route.inertia("/misc/about", "about", {"updated": "2026-10-01"}).name("misc.about")

# -- route parameters -------------------------------------------------------------------------

Route.get("/misc/users/{user_id}/posts/{post_id}", [MiscController, "user_post"]).name("misc.user_post")
Route.get("/misc/archive/{year?}", [MiscController, "archive"]).name("misc.archive")
Route.get("/misc/orders/{id}", [MiscController, "order"]).where_number("id").name("misc.order")
Route.get("/misc/tags/{name}", [MiscController, "tag"]).where_alpha("name").name("misc.tag")
Route.get("/misc/files/{uuid}", [MiscController, "file_by_uuid"]).where_uuid("uuid").name("misc.file")
Route.get("/misc/docs/{path}", [MiscController, "doc"]).where("path", r".*").name("misc.doc")

# -- request inspection / body ------------------------------------------------------------------

Route.get("/misc/inspect", [MiscController, "inspect"]).name("misc.inspect")
Route.post("/misc/inspect", [MiscController, "inspect"]).name("misc.inspect.post")
Route.post("/misc/body", [MiscController, "echo_body"]).middleware("bodypeek").name("misc.body")
Route.post("/misc/upload", [MiscController, "upload"]).name("misc.upload")

# -- response() builder ---------------------------------------------------------------------

Route.get("/misc/json", [MiscController, "json_response"]).name("misc.json")
Route.get("/misc/no-content", [MiscController, "no_content"]).name("misc.no_content")
Route.get("/misc/download", [MiscController, "download_action"]).name("misc.download")
Route.get("/misc/file", [MiscController, "file_action"]).name("misc.file_response")
Route.get("/misc/stream", [MiscController, "stream_action"]).name("misc.stream")
Route.get("/misc/ping", [MiscController, "ping"]).name("misc.ping")

# -- abort ------------------------------------------------------------------------------------

Route.get("/misc/abort", [MiscController, "abort_action"]).name("misc.abort")
Route.get("/misc/abort-if", [MiscController, "abort_if_action"]).name("misc.abort_if")
Route.get("/misc/abort-unless", [MiscController, "abort_unless_action"]).name("misc.abort_unless")

# -- redirects --------------------------------------------------------------------------------

Route.get("/misc/redirect-to", [MiscController, "redirect_to"]).name("misc.redirect_to")
Route.get("/misc/redirect-named", [MiscController, "redirect_named"]).name("misc.redirect_named")
Route.get("/misc/redirect-back", [MiscController, "redirect_back"]).name("misc.redirect_back")
Route.get("/misc/set-intended", [MiscController, "set_intended"]).name("misc.set_intended")
Route.get("/misc/redirect-intended", [MiscController, "redirect_intended"]).name("misc.redirect_intended")
Route.get("/misc/redirect-away", [MiscController, "redirect_away"]).name("misc.redirect_away")
Route.get("/misc/redirect-flash", [MiscController, "redirect_flash"]).name("misc.redirect_flash")
Route.get("/misc/redirect-flash-dict", [MiscController, "redirect_flash_dict"]).name("misc.redirect_flash_dict")
Route.get("/misc/redirect-errors", [MiscController, "redirect_errors"]).name("misc.redirect_errors")
Route.get("/misc/redirect-errors-bag", [MiscController, "redirect_errors_bag"]).name("misc.redirect_errors_bag")
Route.post("/misc/redirect-with-input", [MiscController, "redirect_with_input"]).name("misc.redirect_with_input")
Route.get("/misc/redirect-fragment", [MiscController, "redirect_fragment"]).name("misc.redirect_fragment")
Route.get("/misc/redirect-cookie", [MiscController, "redirect_cookie"]).name("misc.redirect_cookie")
Route.get("/misc/redirect-without-cookie", [MiscController, "redirect_without_cookie"]).name("misc.redirect_without_cookie")

# -- url() helpers ------------------------------------------------------------------------------

Route.get("/misc/url", [MiscController, "url_action"]).name("misc.url")

# -- signed urls --------------------------------------------------------------------------------

Route.get("/misc/secret/{id}", [MiscController, "secret"]).where_number("id").middleware("signed").name("misc.secret")

# -- middleware pipeline --------------------------------------------------------------------------

Route.get("/mw/order", [MiscController, "noop"]).middleware("mw_a", "mw_b").name("mw.order")
Route.get("/mw/priority", [MiscController, "noop"]).middleware("mw_b", "mw_a").name("mw.priority")
Route.get("/mw/short", [MiscController, "mark_ran"]).middleware("shortcircuit").name("mw.short")
Route.get("/mw/header", [MiscController, "noop"]).middleware("headermutate").name("mw.header")
Route.get("/mw/raise", [MiscController, "noop"]).middleware("raiser").name("mw.raise")
Route.get("/mw/stream", [MiscController, "stream_action"]).middleware("streamingpass").name("mw.stream")
Route.get("/mw/secure", [MiscController, "secure"]).middleware("role:editor,admin").name("mw.secure")

with Route.middleware("adminmw").group():
    Route.get("/mw/admin-group", [MiscController, "noop"]).name("mw.admin_group")

Route.get("/gated", [GatedController, "gated"]).name("gated")
Route.get("/open", [GatedController, "open_action"]).name("open")
Route.get("/gated-no-mw", [GatedController, "gated"]).without_middleware("mw_a").name("gated.nomw")

# -- groups -------------------------------------------------------------------------------------

with Route.prefix("admin").name("admin.").middleware("mw_a").group():
    Route.get("/users", [GroupController, "index"]).name("users.index")
    Route.include("routes/included.py")

    with Route.prefix("reports").name("reports.").group():
        Route.get("/sales", [GroupController, "dashboard"]).name("sales")

with Route.controller(GroupController).group():
    Route.get("/orders/{id}", "show")
    Route.post("/orders", "store")

# -- plain FastAPI router ------------------------------------------------------------------------

_legacy = APIRouter()


@_legacy.get("/legacy/items")
async def _legacy_items() -> list:
    return []


Route.include_router(_legacy)

# -- return-value conversion ----------------------------------------------------------------------

Route.get("/convert/dict", [ConvertController, "as_dict"]).name("convert.dict")
Route.get("/convert/list", [ConvertController, "as_list"]).name("convert.list")
Route.get("/convert/none", [ConvertController, "as_none"]).name("convert.none")
Route.get("/convert/response", [ConvertController, "as_response"]).name("convert.response")
Route.post("/convert/model", [ConvertController, "as_model"]).name("convert.model")
Route.get("/convert/pydantic", [ConvertController, "as_pydantic"]).name("convert.pydantic")

# -- single-action (invokable) controller -----------------------------------------------------------

Route.post("/invoke/{n}", PingInvokable).where_number("n").name("invoke")

# -- fallback (must be last) -----------------------------------------------------------------------

Route.fallback([FallbackController, "not_found"])
