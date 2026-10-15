"""Validates and authenticates a login attempt (T-38). Rate-limited 5/min by email + IP, like
Laravel Fortify's default.
"""

from pydantic import EmailStr

from fastogram.auth import auth
from fastogram.auth.events import Lockout
from fastogram.http import FormRequest
from fastogram.rate_limiting import RateLimiter
from fastogram.validation import ValidationException

MAX_ATTEMPTS = 5
DECAY_SECONDS = 60


class LoginRequest(FormRequest):
    email: EmailStr
    password: str
    remember: bool = False

    def prepare_for_validation(self) -> None:
        self.merge({"email": (self.input("email") or "").lower()})

    async def authenticate(self) -> None:
        key = self.throttle_key()
        if await RateLimiter.too_many_attempts(key, max_attempts=MAX_ATTEMPTS):
            await Lockout(email=self.email, ip=self.request.client_ip()).dispatch()
            seconds = await RateLimiter.available_in(key)
            raise ValidationException(
                {"email": f"Too many login attempts. Please try again in {seconds} seconds."}
            )

        if not await auth().attempt({"email": self.email, "password": self.password}, remember=self.remember):
            await RateLimiter.hit(key, decay_seconds=DECAY_SECONDS)
            raise ValidationException({"email": "These credentials do not match our records."})

        await RateLimiter.clear(key)

    def throttle_key(self) -> str:
        return f"{self.email.lower()}|{self.request.client_ip() or '?'}"
