"""Shares the `appearance` cookie (`light` | `dark` | `system`) as an Inertia prop (T-05).

Laravel's kit uses `View::share('appearance', ...)` so the Blade root template can apply the
`dark` class on first paint before React hydrates. Aso's `InertiaResponse.with_view_data()`
is an instance method on the *specific* response a controller returns, and middleware that runs
before the controller has no handle on that instance yet -- so there is no equivalent ambient
"share with every view" hook for Jinja template variables (see the build report for the full
reasoning). This middleware instead shares `appearance` as a normal Inertia prop via
`aso.inertia.share()` (T-17 "From elsewhere"), so pages can read
`usePage().props.appearance` without an extra cookie read. The anti-flash-of-wrong-theme script
in `resources/views/app.html` reads the cookie directly client-side instead, which needs no
server round-trip and has no flash either.
"""

from aso.http import Middleware, Next, Request, Response
from aso.inertia import share

VALID = {"light", "dark", "system"}


class HandleAppearance(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        value = request.cookie("appearance")
        share("appearance", value if value in VALID else "system")
        return await next(request)
