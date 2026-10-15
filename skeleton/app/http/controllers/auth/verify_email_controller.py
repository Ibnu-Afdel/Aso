"""Marks the signed verification link's target email address as verified (T-38)."""

import hashlib
import hmac

from fastogram.auth import AuthorizationException, auth
from fastogram.auth.events import Verified
from fastogram.http import Controller, redirect
from fastogram.routing import route


class VerifyEmailController(Controller):
    async def __call__(self, id: str, hash: str):
        user = auth().user()
        if user is None or str(user.id) != str(id):
            raise AuthorizationException("Invalid verification link.")
        expected = hashlib.sha1(str(user.email).lower().encode()).hexdigest()  # noqa: S324 - matches Laravel's own format
        if not hmac.compare_digest(expected, hash):
            raise AuthorizationException("Invalid verification link.")
        if not user.has_verified_email():
            await user.mark_email_as_verified()
            await Verified(user).dispatch()
        return redirect(f"{route('dashboard')}?verified=1")
