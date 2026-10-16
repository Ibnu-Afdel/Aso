from __future__ import annotations

import time

from aso.auth import auth
from aso.http import Controller, Request
from aso.http.responses import redirect
from aso.security import hash as hash_
from aso.session import session
from aso.validation import ValidationException


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
