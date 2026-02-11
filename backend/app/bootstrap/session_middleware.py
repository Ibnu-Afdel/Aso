from fastapi import FastAPI, Request, Response

from app.bootstrap.container import get_session_manager


def add_session_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next) -> Response:
        async with get_session_manager().session_scope():
            return await call_next(request)
