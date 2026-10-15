"""Through the real stack (T-46, T-41): a controller dispatches an event -- with one inline and
one queued listener -- from inside `DB.transaction()`, and the queued listener sends mail.
Mirrors the worked example in `docs/guide/T-46-events.md`'s "Testing" section."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "orders_app"


@pytest.fixture
async def client():
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        from fastogram.database import Model
        from fastogram.database.engine import engine

        async with engine().begin() as conn:
            await conn.run_sync(Model.metadata.create_all)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))


async def _create_order(client: httpx.AsyncClient) -> int:
    response = await client.post("/api/orders")
    return response.json()["id"]


async def test_shipping_an_order_runs_both_listeners_after_the_commit(client):
    from fastogram.mail.drivers import array_messages

    from app.listeners import log_shipment, send_shipment_notification

    order_id = await _create_order(client)

    response = await client.post(f"/api/orders/{order_id}/shipment")

    assert response.status_code == 200
    assert response.json() == {"status": "shipped"}
    # The non-queued listener ran inline.
    assert log_shipment.calls == [order_id]
    # The queued listener ran too (sync driver), after the transaction committed, and sent mail.
    assert send_shipment_notification.calls == [order_id]
    messages = array_messages()
    assert len(messages) == 1
    assert messages[0]["to"] == ["buyer@example.com"]
    assert messages[0]["subject"] == f"Your order #{order_id} has shipped"

    # And the order really is persisted as shipped.
    show = await client.get(f"/api/orders/{order_id}")
    assert show.json() == {"status": "shipped"}


async def test_rolled_back_transaction_discards_both_listeners_effects(client):
    from fastogram.mail.drivers import array_messages

    from app.listeners import log_shipment, send_shipment_notification

    order_id = await _create_order(client)

    response = await client.post(f"/api/orders/{order_id}/shipment-and-fail")

    assert response.status_code == 200
    # The inline listener did run (it is not after-commit)...
    assert log_shipment.calls == [order_id]
    # ...but the queued listener's job (after_commit=True) was never sent, so no mail went out.
    assert send_shipment_notification.calls == []
    assert array_messages() == []

    show = await client.get(f"/api/orders/{order_id}")
    assert show.json() == {"status": "pending"}
