"""Profile settings: update name/email, or delete the account (T-38, settings/profile)."""

from fastogram.auth import MustVerifyEmail, auth
from fastogram.http import Controller, Request, redirect
from fastogram.inertia import inertia
from fastogram.routing import route
from fastogram.session import session

from app.http.requests.settings.delete_user_request import DeleteUserRequest
from app.http.requests.settings.profile_update_request import ProfileUpdateRequest


class ProfileController(Controller):
    async def edit(self, request: Request):
        user = request.user()
        return inertia(
            "settings/profile",
            {
                "mustVerifyEmail": isinstance(user, MustVerifyEmail),
                "status": request.query("verified"),
            },
        )

    async def update(self, form: ProfileUpdateRequest):
        user = form.user()
        data = form.validated()
        user.fill(**data)
        if user.is_dirty("email"):
            user.email_verified_at = None
        await user.save()
        return redirect().route("profile.edit")

    async def destroy(self, form: DeleteUserRequest):
        user = form.user()
        await auth().logout()  # must run before the row is gone: it saves a rotated remember_token
        await user.delete()
        session().invalidate()
        session().regenerate_token()
        return redirect().to(route("home"))
