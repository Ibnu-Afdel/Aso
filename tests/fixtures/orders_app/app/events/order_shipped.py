from aso.events import Event


class OrderShipped(Event):
    def __init__(self, order_id: int) -> None:
        self.order_id = order_id
