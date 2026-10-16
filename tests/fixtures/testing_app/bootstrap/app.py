from aso.foundation import Application, MiddlewareConfig

from app.http.middleware.handle_inertia_requests import HandleInertiaRequests


def middleware(m: MiddlewareConfig) -> None:
    m.web(append=[HandleInertiaRequests])


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .with_middleware(middleware)
        .create()
    )
