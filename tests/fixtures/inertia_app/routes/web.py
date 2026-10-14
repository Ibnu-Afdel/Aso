from fastogram.routing import Route

from app.http.controllers.errors_controller import ErrorsController
from app.http.controllers.page_controller import PageController

Route.get("/kitchen", [PageController, "kitchen"]).name("kitchen")
Route.get("/shared", [PageController, "shared"]).name("shared")
Route.get("/transactions", [PageController, "transactions"]).name("transactions")
Route.post("/logout", [PageController, "logout"]).name("logout")
Route.get("/flash-now", [PageController, "flash_now"]).name("flash_now")
Route.get("/go", [PageController, "go"]).name("go")
Route.get("/missing-page", [PageController, "missing_page"]).name("missing_page")

Route.get("/errors/create", [ErrorsController, "create"]).name("errors.create")
Route.post("/errors", [ErrorsController, "store"]).name("errors.store")
Route.patch("/errors", [ErrorsController, "store"]).name("errors.update")
Route.post("/errors/invite", [ErrorsController, "invite"]).name("errors.invite")
