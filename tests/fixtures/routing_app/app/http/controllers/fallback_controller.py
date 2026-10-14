from fastogram.http import Controller, Request
from fastogram.http import response as response_builder


class FallbackController(Controller):
    async def not_found(self, request: Request):
        return response_builder().json({"fallback": True, "path": request.path()}, status=404)
