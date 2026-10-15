from __future__ import annotations

import time

from fastogram.auth import auth
from fastogram.http import Controller, Request
from fastogram.http.responses import redirect
from fastogram.security import hash as hash_
from fastogram.session import session
from fastogram.validation import ValidationException


class ConfirmPasswordController(Controller):
    async def create(self) -> dict:
        return {"page": "confirm-password"}

    async def store(self, request: Request):
        data = await request.input()
        user = auth().user()
        if user is None or not hash_.check(str(data.get("password", "")), user.password):
            raise ValidationException({"password": "The password is incorrect."})
        session().put("auth.password_confirmed_at", time.time())
        return redirect().intended("/")
