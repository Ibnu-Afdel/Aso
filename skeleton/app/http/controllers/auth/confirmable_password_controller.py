"""Confirms the current user's password before a sensitive action (T-38)."""

import time

from fastogram.auth import auth
from fastogram.http import Controller, redirect
from fastogram.inertia import inertia
from fastogram.security import hash as hash_
from fastogram.session import session
from fastogram.validation import ValidationException

from app.http.requests.auth.confirm_password_request import ConfirmPasswordRequest


class ConfirmablePasswordController(Controller):
    async def show(self):
        return inertia("auth/confirm-password")

    async def store(self, form: ConfirmPasswordRequest):
        user = auth().user()
        if user is None or not hash_.check(form.password, user.password):
            raise ValidationException({"password": "The password is incorrect."})
        session().put("auth.password_confirmed_at", time.time())
        return redirect().intended("/")
