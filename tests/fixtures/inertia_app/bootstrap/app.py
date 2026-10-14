from fastogram.foundation import Application, MiddlewareConfig

from app.http.middleware.handle_inertia_requests import HandleInertiaRequests
from app.http.middleware.share_feature_flag import ShareFeatureFlag


def middleware(m: MiddlewareConfig) -> None:
    m.web(append=[ShareFeatureFlag, HandleInertiaRequests])


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py")
        .with_middleware(middleware)
        .create()
    )
