"""API routes (T-10): stateless JSON, no session/CSRF, prefixed with `/api`.

No routes ship by default (v1 has no API token guard, D-026). Add your own stateless JSON
endpoints and webhooks here.
"""

from aso.routing import Route  # noqa: F401
