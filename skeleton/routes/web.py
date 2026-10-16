"""Web routes (T-10): session + CSRF + Inertia. Mirrors the Laravel React starter kit's
`routes/web.php`.
"""

from aso.routing import Route

from app.http.controllers.dashboard_controller import DashboardController

Route.inertia("/", "welcome").name("home")

with Route.middleware("auth", "verified").group():
    Route.get("/dashboard", [DashboardController, "show"]).name("dashboard")

Route.include("routes/auth.py")
Route.include("routes/settings.py")
