from fastogram.routing import Route

from app.http.controllers.error_controller import ErrorController

Route.get("/authn", [ErrorController, "authn"])
Route.get("/authz", [ErrorController, "authz"])
Route.get("/model-missing", [ErrorController, "model_missing"])
Route.get("/throttle", [ErrorController, "throttle"])
Route.post("/validation", [ErrorController, "validation_ep"])
