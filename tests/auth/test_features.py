"""Unit test for `features.enabled()` (T-38): reads `config("auth.features")`."""

from __future__ import annotations

from aso.auth import features
from aso.config import set_config


def test_enabled_checks_the_configured_feature_list():
    set_config("auth.features", ["registration", "reset_passwords"])
    assert features.enabled("registration") is True
    assert features.enabled("email_verification") is False


def test_enabled_is_false_when_unset():
    set_config("auth.features", None)
    assert features.enabled("registration") is False
