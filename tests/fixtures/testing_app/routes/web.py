from aso.routing import Route

from app.http.controllers.post_controller import PostController

Route.get("/posts", [PostController, "index"]).name("posts.index")
Route.get("/posts/create", [PostController, "create"]).name("posts.create")
Route.post("/posts", [PostController, "store"]).name("posts.store")
Route.get("/posts/{post}", [PostController, "show"]).name("posts.show")
Route.get("/guarded", [PostController, "index"]).middleware("auth").name("guarded")
