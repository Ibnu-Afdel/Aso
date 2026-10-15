"""The private dashboard landing page (T-05)."""

from fastogram.http import Controller
from fastogram.inertia import inertia


class DashboardController(Controller):
    async def show(self):
        return inertia("dashboard")
