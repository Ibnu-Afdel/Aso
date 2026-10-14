from fastogram.foundation import Application
from fastogram.rate_limiting import Limit, RateLimiter


def register_limiters() -> None:
    RateLimiter.for_("api", lambda request: Limit.per_minute(3).by(request.client_ip()))
    RateLimiter.for_("none", lambda request: Limit.none())


def create_app():
    register_limiters()
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .create()
    )
