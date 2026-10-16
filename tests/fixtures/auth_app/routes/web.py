from aso.routing import Route

from app.http.controllers.confirm_password_controller import ConfirmPasswordController
from app.http.controllers.dashboard_controller import DashboardController
from app.http.controllers.password_reset_controller import PasswordResetController
from app.http.controllers.post_controller import PostController
from app.http.controllers.registration_controller import RegistrationController
from app.http.controllers.session_controller import SessionController
from app.http.controllers.verification_controller import VerificationController

Route.get("/login", [SessionController, "create"]).name("login").middleware("guest")
Route.post("/login", [SessionController, "store"]).name("login.store")
Route.post("/logout", [SessionController, "destroy"]).name("logout").middleware("auth")
Route.post("/logout-other-devices", [SessionController, "logout_other_devices"]).name("logout.other").middleware("auth")

Route.post("/register", [RegistrationController, "store"]).name("register")

with Route.middleware("auth").group():
    Route.get("/dashboard", [DashboardController, "show"]).name("dashboard")

with Route.middleware("auth", "verified").group():
    Route.get("/profile", [DashboardController, "profile"]).name("profile")

Route.delete("/account", [DashboardController, "destroy_account"]).name("account.destroy") \
    .middleware("auth", "password.confirm")

Route.get("/user/confirm-password", [ConfirmPasswordController, "create"]).name("password.confirm").middleware("auth")
Route.post("/user/confirm-password", [ConfirmPasswordController, "store"]).name("password.confirm.store").middleware("auth")

Route.get("/forgot-password", [PasswordResetController, "create"]).name("password.request")
Route.post("/forgot-password", [PasswordResetController, "send"]).name("password.email")
Route.get("/reset-password/{token}", [PasswordResetController, "show"]).name("password.reset")
Route.post("/reset-password", [PasswordResetController, "store"]).name("password.update")

Route.get("/email/verify", [VerificationController, "notice"]).name("verification.notice").middleware("auth")
Route.get("/email/verify/{id}/{hash}", [VerificationController, "verify"]).name("verification.verify") \
    .middleware("auth", "signed")
Route.post("/email/verification-notification", [VerificationController, "send"]).name("verification.send") \
    .middleware("auth")

with Route.middleware("auth").group():
    Route.get("/posts/{post}", [PostController, "show"]).name("posts.show")
    Route.get("/posts/{post}/edit", [PostController, "edit"]).name("posts.edit").middleware("can:update,post")
