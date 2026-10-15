"""Settings routes (T-38), included from `routes/web.py`.

Note (deviation from the literal `settings/password` page name used in some early drafts of
T-05/T-38): the current Laravel React starter kit merged password management into a single
`settings/security` page (together with two-factor auth and passkeys, both Phase 5 per D-009).
Since FastoGram does not ship 2FA/passkeys in v1, `SecurityController.edit` renders
`settings/security` with only the `passwordRules` prop; the frontend port can simplify the kit's
`security.tsx` accordingly. See the build report for the full reasoning.
"""

from fastogram.routing import Route

from app.http.controllers.settings.profile_controller import ProfileController
from app.http.controllers.settings.security_controller import SecurityController

Route.get("/settings/profile", [ProfileController, "edit"]).name("profile.edit").middleware("auth")
Route.patch("/settings/profile", [ProfileController, "update"]).name("profile.update").middleware("auth")
Route.delete("/settings/profile", [ProfileController, "destroy"]).name("profile.destroy").middleware(
    "auth", "password.confirm"
)

Route.get("/settings/security", [SecurityController, "edit"]).name("security.edit").middleware("auth")
Route.put("/settings/password", [SecurityController, "update"]).name("user-password.update").middleware(
    "auth", "throttle:6,1"
)

Route.inertia("/settings/appearance", "settings/appearance").name("appearance.edit").middleware("auth")
