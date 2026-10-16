from aso.http import Controller, Request
from aso.http import response as response_builder


class FallbackController(Controller):
    async def not_found(self, request: Request):
        return response_builder().json({"fallback": True, "path": request.path()}, status=404)
