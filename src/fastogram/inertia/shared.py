"""`share()` (T-17 "From elsewhere"): add a prop to the current request's shared props.

Packages and middleware can share values without editing `HandleInertiaRequests`. `share()` only
affects the current request: it writes into `context.require().shared`, which `InertiaResponse`
merges under the middleware's own `share()`/`share_once()` output and under page props.
"""

from __future__ import annotations

from typing import Any

from fastogram import context


def share(key: str | dict[str, Any], value: Any = None) -> None:
    ctx = context.require()
    items = key if isinstance(key, dict) else {key: value}
    ctx.shared.update(items)
