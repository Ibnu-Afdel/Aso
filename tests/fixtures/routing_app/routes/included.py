"""Loaded by `Route.include("routes/included.py")`: inherits the groups open at the call site (T-10)."""

from aso.routing import Route

from app.http.controllers.group_controller import GroupController

Route.get("/included", [GroupController, "dashboard"]).name("included")
