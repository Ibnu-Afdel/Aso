"""Contextual keyword args, request-id correlation, and redaction (T-22)."""

from __future__ import annotations

import pytest

from aso import context
from aso.log import log
from aso.log.testing import LogCapture


def test_context_kwargs_are_attached_to_the_record():
    with LogCapture() as logs:
        log.info("Order created", order_id=42, user_id=7)
    assert logs.has("Order created")
    assert logs.records[0]["order_id"] == 42
    assert logs.records[0]["user_id"] == 7


def test_request_id_is_dash_outside_a_request():
    with LogCapture() as logs:
        log.info("no request here")
    assert logs.records[0]["request_id"] == "-"


def test_request_id_is_pulled_from_the_active_request_context():
    scope = {"type": "http", "state": {"request_id": "abc123"}}
    ctx = context.RequestContext(scope=scope)
    token = context.enter(ctx)
    try:
        with LogCapture() as logs:
            log.info("inside a request")
    finally:
        context.leave(token)
    assert logs.records[0]["request_id"] == "abc123"


def test_default_redacted_keys():
    with LogCapture() as logs:
        log.info("login attempt", password="super-secret", token="abc", username="bob")
    record = logs.records[0]
    assert record["password"] == "[redacted]"
    assert record["token"] == "[redacted]"
    assert record["username"] == "bob"


def test_redaction_is_case_insensitive_on_the_key():
    with LogCapture() as logs:
        log.info("x", Password="secret", AUTHORIZATION="Bearer xyz")
    record = logs.records[0]
    assert record["Password"] == "[redacted]"
    assert record["AUTHORIZATION"] == "[redacted]"


def test_redact_list_is_configurable(monkeypatch: pytest.MonkeyPatch):
    from aso.config import set_config

    set_config("logging.redact", ["ssn"])
    try:
        with LogCapture() as logs:
            log.info("x", ssn="123-45-6789", password="not-redacted-now")
        record = logs.records[0]
        assert record["ssn"] == "[redacted]"
        assert record["password"] == "not-redacted-now"
    finally:
        set_config("logging.redact", None)
