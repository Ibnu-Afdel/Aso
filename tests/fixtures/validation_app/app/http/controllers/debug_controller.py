from aso.http import Controller
from aso.session import session


class DebugController(Controller):
    """Test-only endpoint: dump the raw session so tests can check flashed error bags / old input
    directly, without depending on the (separately owned) Inertia error-bag prop rendering."""

    async def session_dump(self):
        return {
            "errors": session().get("errors") or {},
            "old_input": session().get("_old_input") or {},
        }
