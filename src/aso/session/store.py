"""The `Session` object (T-18): the full Laravel-`Store`-style API.

Pure data: no I/O. `StartSession` (`middleware.py`) loads one of these from a driver, puts it in
the request context, and persists it again on the way out. Values stored here must be
JSON-serialisable -- `put()` (and anything that calls it) raises `TypeError` immediately for
anything else, so a mistake surfaces at the call site instead of when the driver tries to encode
the payload.
"""

from __future__ import annotations

import copy
import json
import secrets
import time
from typing import Any


def new_id() -> str:
    """A fresh session id: `secrets.token_urlsafe(30)`, 40 characters, like Laravel's."""
    return secrets.token_urlsafe(30)


def _empty_flash() -> dict[str, list[str]]:
    return {"old": [], "new": []}


def _ensure_json_serialisable(value: Any) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Session values must be JSON-serialisable; got {type(value).__name__}. "
            "Store an id, not a model or other object."
        ) from exc


def _dig(data: dict[str, Any], key: str, default: Any = None) -> Any:
    node: Any = data
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


def _dig_exists(data: dict[str, Any], key: str) -> bool:
    node: Any = data
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False
    return True


def _set_dot(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def _forget_dot(data: dict[str, Any], key: str) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            return
        node = nxt
    node.pop(parts[-1], None)


class Session:
    """One request's session. `aso.session.session()` returns the active one."""

    def __init__(
        self,
        id: str,
        data: dict[str, Any] | None = None,
        *,
        is_new: bool = True,
        last_activity: int | None = None,
    ) -> None:
        self._id = id
        self.data: dict[str, Any] = data if data is not None else {}
        self.data.setdefault("_flash", _empty_flash())
        self.is_new = is_new
        self.dirty = is_new
        self.previous_id: str | None = None
        self.destroy_previous = False
        self.last_activity = last_activity if last_activity is not None else int(time.time())
        if "_token" not in self.data:
            self.regenerate_token()

    def id(self) -> str:
        return self._id

    # ------------------------------------------------------------ reading

    def get(self, key: str, default: Any = None) -> Any:
        return _dig(self.data, key, default)

    def has(self, key: str) -> bool:
        """Present *and* not `None` (Laravel's `has`)."""
        return self.get(key) is not None

    def exists(self, key: str) -> bool:
        """Present, even if its value is `None`."""
        return _dig_exists(self.data, key)

    def missing(self, key: str) -> bool:
        return not self.exists(key)

    def all(self) -> dict[str, Any]:
        return self.data

    def only(self, *keys: str) -> dict[str, Any]:
        return {k: self.data[k] for k in keys if k in self.data}

    def except_(self, *keys: str) -> dict[str, Any]:
        excluded = set(keys)
        return {k: v for k, v in self.data.items() if k not in excluded}

    # ------------------------------------------------------------ writing

    def put(self, key: str | dict[str, Any], value: Any = None) -> None:
        """`put("a", 1)` or `put({"a": 1, "b": 2})`. Dot notation reaches into nested dicts."""
        items = key if isinstance(key, dict) else {key: value}
        for v in items.values():
            _ensure_json_serialisable(v)
        for k, v in items.items():
            _set_dot(self.data, k, v)
        self.dirty = True

    def push(self, key: str, value: Any) -> None:
        """Append `value` to the list at `key` (created empty if missing)."""
        _ensure_json_serialisable(value)
        current = self.get(key)
        if current is None:
            current = []
            _set_dot(self.data, key, current)
        if not isinstance(current, list):
            raise TypeError(f"Cannot push onto session key {key!r}: it is not a list.")
        current.append(value)
        self.dirty = True

    def pull(self, key: str, default: Any = None) -> Any:
        """Read then delete."""
        value = self.get(key, default)
        self.forget(key)
        return value

    def forget(self, *keys: str) -> None:
        for key in keys:
            _forget_dot(self.data, key)
        self.dirty = True

    def flush(self) -> None:
        """Remove everything, including the CSRF token and flash state."""
        self.data = {}
        self.dirty = True

    def increment(self, key: str, amount: int = 1) -> int:
        value = int(self.get(key, 0) or 0) + amount
        self.put(key, value)
        return value

    def decrement(self, key: str, amount: int = 1) -> int:
        return self.increment(key, -amount)

    # ------------------------------------------------------------ flash (Laravel `Store` semantics)

    def _flash_dict(self) -> dict[str, list[str]]:
        return self.data.setdefault("_flash", _empty_flash())

    def flash(self, key: str, value: Any = True) -> None:
        """Available now and on the next request."""
        self.put(key, value)
        flash = self._flash_dict()
        if key not in flash["new"]:
            flash["new"].append(key)
        if key in flash["old"]:
            flash["old"].remove(key)

    def now(self, key: str, value: Any) -> None:
        """Available only for the rest of *this* request."""
        self.put(key, value)
        flash = self._flash_dict()
        if key not in flash["old"]:
            flash["old"].append(key)

    def reflash(self) -> None:
        """Keep all current flash data for one more request."""
        flash = self._flash_dict()
        flash["new"] = list(dict.fromkeys([*flash["new"], *flash["old"]]))
        flash["old"] = []
        self.dirty = True

    def keep(self, *keys: str) -> None:
        """Keep only these flash keys for one more request."""
        flash = self._flash_dict()
        for key in keys:
            if key not in flash["new"]:
                flash["new"].append(key)
            if key in flash["old"]:
                flash["old"].remove(key)
        self.dirty = True

    def age_flash(self) -> None:
        """`Illuminate\\Session\\Store::ageFlashData()`: forget `_flash.old`, rotate `new` -> `old`."""
        flash = self._flash_dict()
        changed = bool(flash["old"]) or bool(flash["new"])
        for key in flash["old"]:
            self.data.pop(key, None)
        flash["old"], flash["new"] = flash["new"], []
        if changed:
            self.dirty = True

    # ------------------------------------------------------------ token / id

    def token(self) -> str:
        if "_token" not in self.data:
            self.regenerate_token()
        return self.data["_token"]

    def regenerate_token(self) -> None:
        self.data["_token"] = new_id()
        self.dirty = True

    def regenerate(self, destroy: bool = False) -> None:
        """New session id and new CSRF token. Keeps the data. `destroy=True` also drops the old row."""
        self.previous_id = self._id
        self.destroy_previous = self.destroy_previous or destroy
        self._id = new_id()
        self.dirty = True
        self.regenerate_token()

    def invalidate(self) -> None:
        """Remove all data and issue a new session id (old row destroyed)."""
        self.flush()
        self.regenerate(destroy=True)

    # ------------------------------------------------------------ misc

    def snapshot(self) -> dict[str, Any]:
        """A deep copy of `data`, for drivers that must not hand out a live reference."""
        return copy.deepcopy(self.data)
