from __future__ import annotations

from fastogram.auth import password_broker
from fastogram.http import Controller, Request
from fastogram.validation import ValidationException


class PasswordResetController(Controller):
    async def create(self, request: Request) -> dict:
        email = request.query("email", "")
        return {"page": "forgot-password", "email": email}

    async def send(self, request: Request) -> dict:
        data = await request.input()
        status = await password_broker().send_reset_link(str(data.get("email", "")).strip().lower())
        if status == "throttled":
            raise ValidationException({"email": "Please wait before retrying."})
        return {"status": status}

    async def show(self, request: Request, token: str) -> dict:
        return {"page": "reset-password", "token": token, "email": request.query("email", "")}

    async def store(self, request: Request) -> dict:
        data = await request.input()
        ok = await password_broker().reset(
            str(data.get("email", "")).strip().lower(),
            str(data.get("token", "")),
            str(data.get("password", "")),
        )
        if not ok:
            raise ValidationException({"email": "This password reset token is invalid."})
        return {"status": "reset"}
