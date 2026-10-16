from aso.auth import AuthenticationException, AuthorizationException
from aso.database import ModelNotFound
from aso.exceptions import ThrottleRequestsException
from aso.http import Controller
from aso.inertia import inertia

from app.exceptions.app_error import AppError, SpecificError
from app.exceptions.orders import DontReportMe, InvalidOrder, QuietOrder
from app.exceptions.payment_declined import PaymentDeclined
from app.http.requests.store_thing_request import StoreThingRequest


class ErrorController(Controller):
    async def login(self):
        return inertia("auth/login")

    async def home(self):
        return inertia("home")

    async def authz(self):
        raise AuthorizationException("You may not view this invoice.")

    async def authn(self):
        raise AuthenticationException()

    async def authn_custom(self):
        raise AuthenticationException(redirect_to="/custom-login")

    async def throttle(self):
        raise ThrottleRequestsException(retry_after=30)

    async def payment(self):
        raise PaymentDeclined("Your card was declined.")

    async def boom(self):
        raise RuntimeError("kaboom")

    async def app_error(self):
        raise AppError("generic app error")

    async def specific_error(self):
        raise SpecificError("specific app error")

    async def dont_report_me(self):
        raise DontReportMe("nothing to see here")

    async def invalid_order(self):
        raise InvalidOrder(order_id=77)

    async def quiet_order(self):
        raise QuietOrder("hush")

    async def model_missing(self):
        raise ModelNotFound("Invoice", 42)

    async def validation_ep(self, form: StoreThingRequest):
        return {"ok": True}
