from aso.database.db import DB
from aso.http import Controller

from app.events.order_shipped import OrderShipped
from app.models.order import Order


class OrderShipmentController(Controller):
    """Through the real stack (T-46, T-41): dispatches an event with one inline and one queued
    listener from inside `DB.transaction()`."""

    async def create_order(self):
        order = await Order.create(status="pending", customer_email="buyer@example.com")
        return {"id": order.id}

    async def store(self, order: Order):
        async with DB.transaction():
            await order.update(status="shipped")
            await OrderShipped(order_id=order.id).dispatch()
        return {"status": order.status}

    async def store_and_fail(self, order: Order):
        """Same as `store`, but the transaction rolls back: neither listener's effect (the
        queued mail, dispatched via `DB.after_commit`) should survive. Does not read `order`
        again after the rollback: SQLAlchemy expires its attributes on a savepoint rollback, and
        a sync attribute access on an expired async-ORM instance would need an explicit refresh;
        the test re-fetches the order itself through `show` instead."""

        class Boom(Exception):
            pass

        try:
            async with DB.transaction():
                await order.update(status="shipped")
                await OrderShipped(order_id=order.id).dispatch()
                raise Boom
        except Boom:
            pass
        return {"status": "attempted"}

    async def show(self, order: Order):
        return {"status": order.status}
