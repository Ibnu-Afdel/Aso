"""Shows the "verify your email" notice, or skips straight to the dashboard (T-38)."""

from fastogram.auth import auth
from fastogram.http import Controller, redirect
from fastogram.inertia import inertia
from fastogram.routing import route
from fastogram.session import session


class EmailVerificationPromptController(Controller):
    async def __call__(self):
        user = auth().user()
        if user is not None and user.has_verified_email():
            return redirect().to(route("dashboard"))
        return inertia("auth/verify-email", {"status": session().get("status")})
