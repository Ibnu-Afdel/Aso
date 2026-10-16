from datetime import timedelta

from aso.http import Controller
from aso.inertia import (
    always,
    clear_history,
    deep_merge,
    defer,
    inertia,
    location,
    merge,
    once,
    optional,
    scroll,
)

STATE = {"views": 0}


def _boom() -> list[str]:
    raise RuntimeError("activity feed is down")


class PageController(Controller):
    async def kitchen(self):
        STATE["views"] += 1
        return inertia(
            "kitchen",
            {
                "title": "Hello",
                "stats": always(lambda: {"views": STATE["views"]}),
                "export_preview": optional(lambda: {"ready": True}),
                "permissions": defer(lambda: ["read", "write"]),
                "teams": defer(lambda: ["A", "B"], group="attributes"),
                "projects": defer(lambda: ["P1"], group="attributes"),
                "activity": defer(_boom, rescue=True),
                "posts": merge({"data": [{"id": 1, "title": "a"}], "page": 1}).append("data", match_on="id"),
                "chat": deep_merge({"messages": [{"id": 1, "text": "hi"}]}).match_on("messages.id"),
                "plans": once(lambda: ["basic", "pro"]),
                "rates": once(lambda: {"usd": 1}).until(timedelta(days=1)),
                "member_roles": once(lambda: ["admin"]).as_("roles"),
                "flags": once(lambda: {"beta": True}).fresh(True),
                "feed": scroll({"data": [{"id": 1}], "next_page": 2}),
            },
        )

    async def shared(self):
        return inertia("shared", {})

    async def transactions(self):
        return inertia("shared", {"amount": 42}).encrypt_history()

    async def logout(self):
        from aso.http import redirect

        clear_history()
        return redirect("/")

    async def flash_now(self):
        return inertia("shared", {}).with_flash("success", "Saved.")

    async def go(self):
        return location("https://example.com/external")

    async def missing_page(self):
        return inertia("does/not/exist", {})
