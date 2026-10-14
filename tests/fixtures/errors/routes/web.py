from fastogram.routing import Route

from app.http.controllers.error_controller import ErrorController

Route.get("/login", [ErrorController, "login"]).name("login")
Route.get("/home", [ErrorController, "home"]).name("home")
Route.get("/authz", [ErrorController, "authz"])
Route.get("/authn", [ErrorController, "authn"])
Route.get("/authn-custom", [ErrorController, "authn_custom"])
Route.get("/throttle", [ErrorController, "throttle"])
Route.get("/payment", [ErrorController, "payment"])
Route.get("/boom", [ErrorController, "boom"])
Route.get("/app-error", [ErrorController, "app_error"])
Route.get("/specific-error", [ErrorController, "specific_error"])
Route.get("/dont-report-me", [ErrorController, "dont_report_me"])
Route.get("/invalid-order", [ErrorController, "invalid_order"])
Route.get("/quiet-order", [ErrorController, "quiet_order"])
Route.get("/model-missing", [ErrorController, "model_missing"])
Route.get("/crash-before-inertia", [ErrorController, "home"])
Route.post("/validation", [ErrorController, "validation_ep"])
Route.put("/validation", [ErrorController, "validation_ep"])
