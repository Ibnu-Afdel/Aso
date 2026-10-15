from fastogram.mail import Content, Envelope, Mailable

from app.models.order import Order


class ShipmentConfirmation(Mailable):
    def __init__(self, order: Order) -> None:
        self.order = order

    def envelope(self) -> Envelope:
        return Envelope(subject=f"Your order #{self.order.id} has shipped")

    def content(self) -> Content:
        return Content(view="mail/shipment_confirmation.html", with_={"order": self.order})
