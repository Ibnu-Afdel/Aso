from fastogram.config import env
from fastogram.foundation import Application, MiddlewareConfig


def middleware(m: MiddlewareConfig) -> None:
    except_ = [p for p in env("CSRF_EXCEPT", "").split(",") if p]
    m.prevent_request_forgery(
        except_=except_,
        origin_only=bool(env("CSRF_ORIGIN_ONLY", False)),
        allow_same_site=bool(env("CSRF_ALLOW_SAME_SITE", False)),
    )


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py")
        .with_middleware(middleware)
        .create()
    )
