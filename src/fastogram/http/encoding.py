"""Controller return-value conversion (T-13, T-15): the table in "What controllers return"."""

from __future__ import annotations

import inspect
from typing import Any

from starlette.responses import HTMLResponse, JSONResponse, Response


def to_response(result: Any) -> Response:
    """Convert a controller's return value into a Starlette `Response` (T-13, T-15)."""
    if isinstance(result, Response):
        return result
    if result is None:
        return Response(status_code=204)
    if _looks_like_mailable(result):
        html = result.render()
        if inspect.isawaitable(html):
            raise TypeError("Mailable.render() must be synchronous; await it before returning from a controller.")
        return HTMLResponse(html)
    return JSONResponse(jsonable(result))


def jsonable(value: Any) -> Any:
    """FastoGram's JSON encoder: datetimes as ISO 8601, `Decimal` as string, `UUID` as string,
    `Enum` -> value, `Model` -> `to_dict()`, Pydantic -> `model_dump(mode="json")`."""
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="json"))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict) and not isinstance(value, (type, dict, list, tuple)):
        return jsonable(to_dict())
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(value)


def _looks_like_mailable(value: Any) -> bool:
    if isinstance(value, (dict, list, tuple, str, bytes, int, float, bool)) or value is None:
        return False
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return False
    render = getattr(value, "render", None)
    return callable(render) and not hasattr(value, "to_dict")
