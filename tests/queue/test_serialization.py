from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aso.queue import JobNotSerializable
from aso.queue.serialization import decode_args, encode_args, validate_serializable


def test_primitives_pass():
    validate_serializable({"a": 1, "b": "x", "c": 1.5, "d": True, "e": None, "f": [1, 2, {"g": 3}]})


def test_datetime_and_uuid_pass():
    validate_serializable({"at": datetime.now(UTC), "id": uuid4()})


def test_non_string_dict_key_raises():
    with pytest.raises(JobNotSerializable):
        validate_serializable({1: "x"})


def test_arbitrary_object_raises():
    class Thing:
        pass

    with pytest.raises(JobNotSerializable):
        validate_serializable({"thing": Thing()})


def test_nested_list_reports_a_path_in_the_message():
    class Thing:
        pass

    with pytest.raises(JobNotSerializable, match=r"items\[1\]\.bad"):
        validate_serializable({"items": [{"ok": 1}, {"bad": Thing()}]})


def test_encode_decode_round_trips_datetime_and_uuid():
    at = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    uid = uuid4()
    encoded = encode_args({"at": at, "id": uid, "n": 3})
    decoded = decode_args(encoded)
    assert decoded["at"] == at
    assert decoded["id"] == uid
    assert decoded["n"] == 3
