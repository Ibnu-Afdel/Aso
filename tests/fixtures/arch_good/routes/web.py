from __future__ import annotations

from fastogram.inertia import inertia
from fastogram.routing import Route

from app.http.controllers.post_controller import PostController

Route.get("/posts", [PostController, "index"]).name("posts.index")


def render_posts() -> object:
    return inertia("posts/index", {"posts": []})
