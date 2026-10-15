"""Authentication routes (T-38), included from `routes/web.py`. Mirrors the Laravel React
starter kit's `routes/auth.php`: full registration, login, logout, password reset, email
verification and password-confirmation flows.
"""

from fastogram.auth import features
from fastogram.routing import Route

from app.http.controllers.auth.authenticated_session_controller import AuthenticatedSessionController
from app.http.controllers.auth.confirmable_password_controller import ConfirmablePasswordController
from app.http.controllers.auth.email_verification_notification_controller import (
    EmailVerificationNotificationController,
)
from app.http.controllers.auth.email_verification_prompt_controller import EmailVerificationPromptController
from app.http.controllers.auth.new_password_controller import NewPasswordController
from app.http.controllers.auth.password_reset_link_controller import PasswordResetLinkController
from app.http.controllers.auth.registered_user_controller import RegisteredUserController
from app.http.controllers.auth.verify_email_controller import VerifyEmailController

if features.enabled("registration"):
    Route.get("/register", [RegisteredUserController, "create"]).name("register").middleware("guest")
    Route.post("/register", [RegisteredUserController, "store"]).name("register.store").middleware("guest")

Route.get("/login", [AuthenticatedSessionController, "create"]).name("login").middleware("guest")
Route.post("/login", [AuthenticatedSessionController, "store"]).name("login.store").middleware("guest")
Route.post("/logout", [AuthenticatedSessionController, "destroy"]).name("logout").middleware("auth")

if features.enabled("reset_passwords"):
    Route.get("/forgot-password", [PasswordResetLinkController, "create"]).name("password.request").middleware(
        "guest"
    )
    Route.post("/forgot-password", [PasswordResetLinkController, "store"]).name("password.email").middleware(
        "guest"
    )
    Route.get("/reset-password/{token}", [NewPasswordController, "create"]).name("password.reset").middleware(
        "guest"
    )
    Route.post("/reset-password", [NewPasswordController, "store"]).name("password.update").middleware("guest")

if features.enabled("email_verification"):
    Route.get("/email/verify", [EmailVerificationPromptController, "__call__"]).name(
        "verification.notice"
    ).middleware("auth")
    Route.get("/email/verify/{id}/{hash}", [VerifyEmailController, "__call__"]).name(
        "verification.verify"
    ).middleware("auth", "signed")
    Route.post("/email/verification-notification", [EmailVerificationNotificationController, "store"]).name(
        "verification.send"
    ).middleware("auth", "throttle:6,1")

Route.get("/user/confirm-password", [ConfirmablePasswordController, "show"]).name("password.confirm").middleware(
    "auth"
)
Route.post("/user/confirm-password", [ConfirmablePasswordController, "store"]).name(
    "password.confirm.store"
).middleware("auth")
