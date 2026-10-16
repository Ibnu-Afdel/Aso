from aso.routing import Route

from app.http.controllers.post_controller import PostController

Route.get("/posts/{post_id}", [PostController, "api_show"])
