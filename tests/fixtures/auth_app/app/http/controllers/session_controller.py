"""Login/logout (T-38). Mirrors `AuthenticatedSessionController` + `LoginRequest.authenticate()`
from the guide, inlined here since controllers/form requests are app-skeleton code, not library
code -- this fixture app exists only to drive the auth *library* through the real stack."""

from __future__ import annotations

from aso.auth import auth, features
from aso.auth.events import Lockout
from aso.http import Controller, Request
from aso.http.responses import redirect
from aso.rate_limiting import RateLimiter
from aso.routing import route
from aso.session import session
from aso.validation import ValidationException


def _throttle_key(email: str, request: Request) -> str:
    return f"{email}|{request.client_ip() or '?'}"


class SessionController(Controller):
    async def create(self) -> dict:
        return {"page": "login", "can_reset_password": features.enabled("reset_passwords")}

    async def store(self, request: Request):
        data = await request.input()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        remember = bool(data.get("remember", False))
        key = _throttle_key(email, request)

        if await RateLimiter.too_many_attempts(key, max_attempts=5):
            await Lockout(email=email, ip=request.client_ip()).dispatch()
            seconds = await RateLimiter.available_in(key)
            raise ValidationException({"email": f"Too many login attempts. Please try again in {seconds} seconds."})

        if not await auth().attempt({"email": email, "password": password}, remember=remember):
            await RateLimiter.hit(key, decay_seconds=60)
            raise ValidationException({"email": "These credentials do not match our records."})

        await RateLimiter.clear(key)
        session().regenerate()
        return redirect().intended(route("dashboard"))

    async def destroy(self) -> dict:
        await auth().logout()
        session().invalidate()
        session().regenerate_token()
        return {"status": "logged-out"}

    async def logout_other_devices(self, request: Request) -> dict:
        data = await request.input()
        ok = await auth().logout_other_devices(str(data.get("password", "")))
        if not ok:
            raise ValidationException({"password": "The password is incorrect."})
        return {"status": "ok"}
