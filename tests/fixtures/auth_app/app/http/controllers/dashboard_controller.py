from __future__ import annotations

from fastogram.auth import auth
from fastogram.http import Controller


class DashboardController(Controller):
    async def show(self) -> dict:
        user = auth().user()
        return {"user_id": user.id, "via_remember": auth().via_remember()}

    async def profile(self) -> dict:
        user = auth().user()
        return {"email": user.email}

    async def destroy_account(self) -> dict:
        user = auth().user()
        await auth().logout()  # must run before the row is gone: it saves a rotated remember_token
        await user.delete()
        return {"status": "deleted"}
