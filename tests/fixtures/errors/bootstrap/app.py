from starlette.responses import PlainTextResponse

from aso.foundation import Application, ExceptionsConfig, MiddlewareConfig

from app.exceptions.app_error import AppError, SpecificError
from app.exceptions.orders import DontReportMe, InvalidOrder, QuietOrder
from app.http.middleware.crash_before_inertia import CrashBeforeInertia
from app.http.middleware.handle_inertia_requests import HandleInertiaRequests

#: test hook: cleared and inspected by tests, filled by the `report(InvalidOrder, ...)` callback.
REPORTED: list[int] = []


def middleware(m: MiddlewareConfig) -> None:
    m.web(append=[CrashBeforeInertia, HandleInertiaRequests])
    m.redirect_guests_to("/login")


def _render_specific(exc, request):
    return PlainTextResponse("handled: specific", status_code=499)


def _tag_response(response, exc, request):
    response.headers["X-Tested"] = "1"
    return response


def exceptions(e: ExceptionsConfig) -> None:
    e.dont_report([DontReportMe])
    e.report(InvalidOrder, lambda exc: REPORTED.append(exc.order_id))
    e.report(QuietOrder, lambda exc: False)
    e.context(lambda: {"tenant": "acme"})
    e.render(AppError, lambda exc, request: None)  # falls through to the built-in 500
    e.render(SpecificError, _render_specific)  # more specific than AppError: must win (MRO order)
    e.respond(_tag_response)
    e.inertia_error_page("error", statuses=[403, 404, 419, 429, 500, 503])


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .with_middleware(middleware)
        .with_exceptions(exceptions)
        .create()
    )
