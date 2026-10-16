import hashlib
from datetime import timedelta

from aso.auth.events import Verified
from aso.events import Event
from aso.routing import url
from aso.testing import TestClient

from database.factories.user_factory import UserFactory


async def test_email_verification_screen_can_be_rendered(client: TestClient) -> None:
    unverified = await UserFactory.new().unverified().create()

    response = await client.acting_as(unverified).get("/email/verify")

    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/verify-email"))


async def test_email_can_be_verified(client: TestClient) -> None:
    Event.fake()
    unverified = await UserFactory.new().unverified().create()
    email_hash = hashlib.sha1(unverified.email.lower().encode()).hexdigest()  # noqa: S324
    signed = url().temporary_signed_route("verification.verify", timedelta(minutes=60), {"id": unverified.id, "hash": email_hash})

    response = await client.acting_as(unverified).get(signed)

    response.assert_redirect()
    # `User.find()` would return the same Python object already cached by this test's db scope
    # (the request ran in its own session) without re-reading its columns; `.refresh()` forces a
    # real reload (T-31).
    await unverified.refresh()
    assert unverified.has_verified_email()
    Event.assert_dispatched(Verified)


async def test_email_is_not_verified_with_invalid_hash(client: TestClient) -> None:
    unverified = await UserFactory.new().unverified().create()
    signed = url().temporary_signed_route(
        "verification.verify", timedelta(minutes=60), {"id": unverified.id, "hash": "wrong-hash"}
    )

    response = await client.acting_as(unverified).get(signed)

    response.assert_forbidden()
    await unverified.refresh()
    assert not unverified.has_verified_email()
