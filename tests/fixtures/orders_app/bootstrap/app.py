from fastogram.events import Event
from fastogram.foundation import Application

from app.events.order_shipped import OrderShipped
from app.listeners.log_shipment import LogShipment
from app.listeners.send_shipment_notification import SendShipmentNotification


def create_app():
    Event.listen(OrderShipped, LogShipment)
    Event.listen(OrderShipped, SendShipmentNotification)

    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .create()
    )
