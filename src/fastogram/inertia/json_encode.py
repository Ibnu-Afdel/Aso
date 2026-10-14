"""JSON conversion for Inertia props (T-16 "Props: what you can pass").

`datetime`/`date` → ISO 8601 strings, `Decimal` → string, `UUID` → string, `Enum` → its value,
Pydantic models → `model_dump(mode="json")`, objects with `to_dict()` → that, recursively.
Everything else falls back to FastAPI's `jsonable_encoder`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict) and not isinstance(value, type):
        return to_jsonable(to_dict())

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump) and not isinstance(value, type):
        return to_jsonable(value.model_dump(mode="json"))

    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(value)
