"""JSON-serialisability checks for job/listener/event arguments (T-42, D-011).

Job (and queued-listener, and queued-event) arguments must be plain JSON values: `str`, `int`,
`float`, `bool`, `None`, `list`/`tuple`, `dict` (string keys) and, as an extension Laravel does
not need, `datetime` and `UUID` (encoded as tagged strings so they round-trip through a real
queue). Anything else -- in particular a `Model` instance -- raises `JobNotSerializable` at
dispatch time, never later in the worker (D-011, A12).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from aso.exceptions.types import JobNotSerializable

_DATETIME_TAG = "__aso_datetime__"
_DATE_TAG = "__aso_date__"
_UUID_TAG = "__aso_uuid__"


def validate_serializable(value: Any, path: str = "") -> None:
    """Raise `JobNotSerializable` if `value` is not made entirely of JSON-safe primitives."""
    if value is None or isinstance(value, (bool, int, float, str, datetime, date, UUID)):
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise JobNotSerializable(
                    f"Job argument {path or '<root>'} has a non-string dict key ({key!r}). "
                    "Job arguments must be JSON-serialisable: pass ids and plain values, not models."
                )
            validate_serializable(item, f"{path}.{key}" if path else key)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_serializable(item, f"{path}[{index}]")
        return
    raise JobNotSerializable(
        f"Job argument {path or '<root>'} is not JSON-serialisable ({type(value).__name__}). "
        "Pass ids and plain values, not model instances -- load the model inside handle()."
    )


def encode_args(args: dict[str, Any]) -> dict[str, Any]:
    """Validate `args`, then return a plain-JSON copy (tagged datetimes/UUIDs) safe to send
    over a real queue (Redis) as text."""
    validate_serializable(args)
    return json.loads(json.dumps(args, default=_tag))


def decode_args(args: dict[str, Any]) -> dict[str, Any]:
    """Reverse of `encode_args`: restore tagged datetimes/UUIDs."""
    return json.loads(json.dumps(args), object_hook=_untag)


def _tag(value: Any) -> Any:
    if isinstance(value, datetime):
        return {_DATETIME_TAG: value.astimezone(UTC).isoformat()}
    if isinstance(value, date):
        return {_DATE_TAG: value.isoformat()}
    if isinstance(value, UUID):
        return {_UUID_TAG: str(value)}
    raise TypeError(value)  # pragma: no cover - validate_serializable already rejected this


def _untag(node: dict[str, Any]) -> Any:
    if _DATETIME_TAG in node:
        return datetime.fromisoformat(node[_DATETIME_TAG])
    if _DATE_TAG in node:
        return date.fromisoformat(node[_DATE_TAG])
    if _UUID_TAG in node:
        return UUID(node[_UUID_TAG])
    return node
