from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.bootstrap.request_context import reset_request_id, set_request_id


def add_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        request_id = str(uuid4())
        token = set_request_id(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response
