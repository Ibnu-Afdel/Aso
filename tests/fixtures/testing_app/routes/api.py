from fastogram.routing import Route

from app.http.controllers.api_post_controller import ApiPostController

Route.get("/posts", [ApiPostController, "index"]).name("api.posts.index")
Route.post("/posts", [ApiPostController, "store"]).name("api.posts.store")
Route.get("/posts/{post}", [ApiPostController, "show"]).name("api.posts.show")
