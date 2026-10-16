from aso.routing import Route

from app.http.controllers.post_controller import PostController

Route.get("/posts", [PostController, "index"]).name("posts.index")
Route.post("/posts", [PostController, "store"]).name("posts.store")
