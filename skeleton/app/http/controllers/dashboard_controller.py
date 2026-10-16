"""The private dashboard landing page (T-05)."""

from aso.http import Controller
from aso.inertia import inertia


class DashboardController(Controller):
    async def show(self):
        return inertia("dashboard")
