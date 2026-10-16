from aso.routing import Route

from app.http.controllers.order_shipment_controller import OrderShipmentController

Route.post("/orders", [OrderShipmentController, "create_order"]).name("orders.create")
Route.get("/orders/{order}", [OrderShipmentController, "show"]).name("orders.show")
Route.post("/orders/{order}/shipment", [OrderShipmentController, "store"]).name("orders.shipment")
Route.post("/orders/{order}/shipment-and-fail", [OrderShipmentController, "store_and_fail"]).name(
    "orders.shipment.fail"
)
