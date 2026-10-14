from fastogram.routing import Route

from app.http.controllers.post_controller import PostController

Route.get("/posts", [PostController, "index"]).name("posts.index")
Route.get("/posts/create", [PostController, "create"]).name("posts.create")
Route.post("/posts", [PostController, "store"]).name("posts.store")
Route.get("/stats", [PostController, "stats"]).name("stats")
Route.get("/boom", [PostController, "boom"]).name("boom")
