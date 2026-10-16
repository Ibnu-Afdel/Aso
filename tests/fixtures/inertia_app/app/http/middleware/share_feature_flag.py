from starlette.responses import Response

from aso.http import Middleware, Next, Request
from aso.inertia import share


class ShareFeatureFlag(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        share("feature_flag", True)
        return await next(request)
