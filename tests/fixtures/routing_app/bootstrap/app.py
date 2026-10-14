from fastogram.foundation import Application, MiddlewareConfig

from app.http.middleware.bodypeek import BodyPeek
from app.http.middleware.handle_inertia_requests import HandleInertiaRequests
from app.http.middleware.header_mutator import HeaderMutator
from app.http.middleware.raiser import Raiser
from app.http.middleware.recording import RecordA, RecordB, RecordC, RecordD
from app.http.middleware.role import RequireRole
from app.http.middleware.short_circuit import ShortCircuit


def middleware(m: MiddlewareConfig) -> None:
    m.web(append=[HandleInertiaRequests])
    m.alias(
        {
            "mw_a": RecordA,
            "mw_b": RecordB,
            "mw_c": RecordC,
            "mw_d": RecordD,
            "role": RequireRole,
            "shortcircuit": ShortCircuit,
            "headermutate": HeaderMutator,
            "raiser": Raiser,
            "bodypeek": BodyPeek,
            "streamingpass": "fastogram.http.middleware:Middleware",
        }
    )
    m.group("adminmw", ["mw_c", "mw_d"])
    m.priority(["mw_a", "mw_b", "bindings"])


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .with_middleware(middleware)
        .create()
    )
