"""`ExceptionsConfig` features: report/dont_report/render (MRO)/respond/context, and an exception
class's own `report()`/`render()` (T-20)."""

from __future__ import annotations

from aso.log.testing import LogCapture

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


# ---------------------------------------------------------------- an exception's own report()/render()


async def test_exception_with_own_render_redirects_back_with_flash(client):
    await client.get("/home", headers={**INERTIA, "Referer": "http://testserver/home"})
    with LogCapture() as logs:
        r = await client.get("/payment", headers={**INERTIA, "Referer": "http://testserver/home"})
    assert r.status_code == 302
    assert r.headers["location"] == "/home"
    r = await client.get("/home", headers=INERTIA)
    assert r.json()["flash"] == {"error": "Your card was declined."}
    # the exception's own `report()` returns False: never logged
    assert not any("PaymentDeclined" in rec["message"] for rec in logs.records)


# ---------------------------------------------------------------- dont_report / report callbacks


async def test_dont_report_suppresses_the_default_log(client):
    with LogCapture() as logs:
        r = await client.get("/dont-report-me", headers=INERTIA)
    assert r.status_code == 500
    assert not any("DontReportMe" in rec["message"] for rec in logs.records)


async def test_report_callback_runs_then_default_log_still_happens(client):
    from bootstrap.app import REPORTED

    with LogCapture() as logs:
        r = await client.get("/invalid-order", headers=INERTIA)
    assert r.status_code == 500
    assert REPORTED == [77]
    assert any("InvalidOrder" in rec["message"] for rec in logs.records)


async def test_report_callback_returning_false_stops_the_default_log(client):
    with LogCapture() as logs:
        r = await client.get("/quiet-order", headers=INERTIA)
    assert r.status_code == 500
    assert not any("QuietOrder" in rec["message"] for rec in logs.records)


async def test_report_attaches_request_metadata_and_context_callback(client):
    with LogCapture() as logs:
        r = await client.get("/invalid-order", headers=INERTIA)
    assert r.status_code == 500
    record = next(rec for rec in logs.records if "InvalidOrder" in rec["message"])
    assert record["method"] == "GET"
    assert record["url"].endswith("/invalid-order")
    assert record["tenant"] == "acme"  # from e.context(lambda: {"tenant": "acme"})
    assert "Traceback" in record["traceback"] or "InvalidOrder" in record["traceback"]


# ---------------------------------------------------------------- render() callbacks, MRO order


async def test_render_callback_returning_none_falls_back_to_the_built_in_500(client):
    r = await client.get("/app-error", headers=INERTIA)
    assert r.status_code == 500
    assert r.json()["component"] == "error"


async def test_more_specific_render_callback_wins_over_a_base_class_one(client):
    r = await client.get("/specific-error")
    assert r.status_code == 499
    assert r.text == "handled: specific"


# ---------------------------------------------------------------- respond() callback


async def test_respond_callback_tags_every_error_response(client):
    r = await client.get("/model-missing", headers=INERTIA)
    assert r.headers["x-tested"] == "1"
    r = await client.get("/app-error")
    assert r.headers["x-tested"] == "1"
