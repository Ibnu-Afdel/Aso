"""Builds the ASGI application (T-06). Uvicorn calls `create_app()` once per worker process."""

from fastogram.auth.events import Registered
from fastogram.events import Event
from fastogram.foundation import Application, ExceptionsConfig, MiddlewareConfig

from app.http.middleware.handle_appearance import HandleAppearance
from app.http.middleware.handle_inertia_requests import HandleInertiaRequests
from app.listeners.send_email_verification_notification import SendEmailVerificationNotification


def middleware(m: MiddlewareConfig) -> None:
    m.web(append=[HandleAppearance, HandleInertiaRequests])


def exceptions(e: ExceptionsConfig) -> None:
    pass


def create_app():
    # Events, gates and named rate limiters are registered here (no service providers in v1, T-06).
    Event.listen(Registered, SendEmailVerificationNotification)

    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", console="routes/console.py", health="/up")
        .with_middleware(middleware)
        .with_exceptions(exceptions)
        .create()
    )
