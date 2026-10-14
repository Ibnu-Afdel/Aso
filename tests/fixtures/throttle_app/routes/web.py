from fastogram.routing import Route

from app.http.controllers.ping_controller import PingController

Route.get("/ping", [PingController, "index"]).middleware("throttle:2,1").name("ping")
Route.get("/ping-named", [PingController, "named"]).middleware("throttle:api").name("ping.named")
Route.get("/ping-unlimited", [PingController, "unlimited"]).middleware("throttle:none").name("ping.unlimited")
