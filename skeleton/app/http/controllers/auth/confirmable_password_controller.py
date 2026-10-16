"""Confirms the current user's password before a sensitive action (T-38)."""

import time

from aso.auth import auth
from aso.http import Controller, redirect
from aso.inertia import inertia
from aso.security import hash as hash_
from aso.session import session
from aso.validation import ValidationException

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
