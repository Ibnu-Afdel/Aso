"""A queued listener (T-46): runs as a `CallQueuedListener` job instead of inline. `after_commit`
is left at its default (`True`), so on `DB.transaction()` it only reaches the worker once the
transaction committed."""

from __future__ import annotations

from aso.mail import Mail

from app.events.order_shipped import OrderShipped
from app.mail.shipment_confirmation import ShipmentConfirmation
from app.models.order import Order

calls: list[int] = []


class SendShipmentNotification:
    queued = True
    queue = "emails"
    tries = 3
    backoff = [10, 60]

    async def handle(self, event: OrderShipped) -> None:
        order = await Order.find(event.order_id)
        if order is None:
            return
        calls.append(order.id)
        await Mail.to(order.customer_email).send(ShipmentConfirmation(order))
