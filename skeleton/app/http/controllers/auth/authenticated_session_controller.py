"""Login and logout (T-38)."""

from fastogram.auth import auth, features
from fastogram.http import Controller, Request, redirect
from fastogram.inertia import clear_history, inertia
from fastogram.routing import route
from fastogram.session import session

from app.http.requests.auth.login_request import LoginRequest


class AuthenticatedSessionController(Controller):
    async def create(self, request: Request):
        return inertia(
            "auth/login",
            {
                "status": session().get("status"),
                "canResetPassword": features.enabled("reset_passwords"),
            },
        )

    async def store(self, form: LoginRequest):
        await form.authenticate()
        session().regenerate()
        return redirect().intended(route("dashboard"))

    async def destroy(self):
        await auth().logout()
        session().invalidate()
        session().regenerate_token()
        clear_history()
        return redirect("/")
