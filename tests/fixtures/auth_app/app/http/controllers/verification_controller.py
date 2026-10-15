from __future__ import annotations

import hashlib
import hmac

from fastogram.auth import auth
from fastogram.auth.events import Verified
from fastogram.exceptions.types import AuthorizationException
from fastogram.http import Controller
from fastogram.http.responses import redirect
from fastogram.routing import route


class VerificationController(Controller):
    async def notice(self) -> dict:
        return {"page": "verify-email"}

    async def verify(self, id: str, hash: str) -> dict:
        user = auth().user()
        if user is None or str(user.id) != str(id):
            raise AuthorizationException("Invalid verification link.")
        expected = hashlib.sha1(str(user.email).lower().encode()).hexdigest()
        if not hmac.compare_digest(expected, hash):
            raise AuthorizationException("Invalid verification link.")
        if not user.has_verified_email():
            await user.mark_email_as_verified()
            await Verified(user).dispatch()
        return redirect(f"{route('dashboard')}?verified=1")

    async def send(self) -> dict:
        user = auth().user()
        if user is not None and not user.has_verified_email():
            await user.send_email_verification_notification()
        return {"status": "sent"}
