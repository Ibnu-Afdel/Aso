"""Registration (T-38). Creating the user is delegated to `CreateNewUser`, which you can edit."""

from fastogram.auth import auth
from fastogram.auth.events import Registered
from fastogram.http import Controller, redirect
from fastogram.inertia import inertia
from fastogram.routing import route
from fastogram.session import session

from app.actions.auth.create_new_user import CreateNewUser
from app.actions.auth.password_validation_rules import PasswordValidationRules
from app.http.requests.auth.register_request import RegisterRequest


class RegisteredUserController(Controller):
    async def create(self):
        return inertia("auth/register", {"passwordRules": PasswordValidationRules().description()})

    async def store(self, form: RegisterRequest):
        user = await CreateNewUser().create(form.validated())
        await Registered(user).dispatch()  # sends the verification email (T-41, T-46)
        await auth().login(user)
        session().regenerate()
        return redirect().to(route("dashboard"))
