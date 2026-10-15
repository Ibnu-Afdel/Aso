from __future__ import annotations

from fastogram.auth import auth
from fastogram.auth.events import Registered
from fastogram.http import Controller, Request
from fastogram.http.responses import redirect
from fastogram.routing import route
from fastogram.session import session
from fastogram.validation import ValidationException

from app.models.user import User


class RegistrationController(Controller):
    async def store(self, request: Request):
        data = await request.input()
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not name or not email or not password:
            raise ValidationException({"email": "name, email and password are required."})
        if await User.where(email=email).first() is not None:
            raise ValidationException({"email": "The email has already been taken."})

        user = await User.create(name=name, email=email, password=password)
        await Registered(user).dispatch()
        await auth().login(user)
        session().regenerate()
        return redirect().to(route("dashboard"))
