from fastogram.routing import Route

from app.http.controllers.misc_controller import MiscController
from app.http.controllers.stub_controllers import ArchiveController, WidgetController

Route.api_resource("widgets", WidgetController)
Route.resource("archives", ArchiveController)

Route.get("/misc/echo", [MiscController, "echo_method"]).name("api.misc.echo")
Route.put("/misc/echo", [MiscController, "echo_method"]).name("api.misc.echo.put")
