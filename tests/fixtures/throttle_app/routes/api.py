from fastogram.routing import Route

from app.http.controllers.ping_controller import PingController

Route.get("/ping", [PingController, "index"]).middleware("throttle:2,1").name("api.ping")
