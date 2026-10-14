"""The `Session` object (T-18).

SEED (spine): flash ageing exactly as Laravel's `Store`, token, basic get/put. The session
package task completes the full T-18 API (dot notation, push/pull/increment, only/except_,
regenerate/invalidate, JSON-only values) and the drivers.
"""

from __future__ import annotations

import copy
import secrets
from typing import Any


def new_id() -> str:
    return secrets.token_urlsafe(30)


class Session:
    def __init__(self, id: str, data: dict[str, Any] | None = None, *, is_new: bool = True) -> None:
        self._id = id
        self.data: dict[str, Any] = data or {}
        self.data.setdefault("_flash", {"old": [], "new": []})
        self.is_new = is_new
        self.dirty = is_new
        self.previous_id: str | None = None
        self.original = copy.deepcopy(self.data)
        if "_token" not in self.data:
            self.regenerate_token()

    def id(self) -> str:
        return self._id

    # -- reading
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def has(self, key: str) -> bool:
        return self.data.get(key) is not None

    def all(self) -> dict[str, Any]:
        return self.data

    # -- writing
    def put(self, key: str, value: Any = None) -> None:
        self.data[key] = value
        self.dirty = True

    def forget(self, *keys: str) -> None:
        for key in keys:
            self.data.pop(key, None)
        self.dirty = True

    # -- flash (Laravel Store semantics)
    def flash(self, key: str, value: Any = True) -> None:
        self.put(key, value)
        flash = self.data["_flash"]
        if key not in flash["new"]:
            flash["new"].append(key)
        if key in flash["old"]:
            flash["old"].remove(key)

    def now(self, key: str, value: Any) -> None:
        self.put(key, value)
        if key not in self.data["_flash"]["old"]:
            self.data["_flash"]["old"].append(key)

    def reflash(self) -> None:
        flash = self.data["_flash"]
        flash["new"] = list(dict.fromkeys([*flash["new"], *flash["old"]]))
        flash["old"] = []
        self.dirty = True

    def age_flash(self) -> None:
        flash = self.data["_flash"]
        for key in flash["old"]:
            self.data.pop(key, None)
        flash["old"], flash["new"] = flash["new"], []
        if flash["old"]:
            self.dirty = True

    # -- token / id
    def token(self) -> str:
        return self.data["_token"]

    def regenerate_token(self) -> None:
        self.data["_token"] = new_id()
        self.dirty = True

    def regenerate(self, destroy: bool = False) -> None:
        self.previous_id = self._id
        self._id = new_id()
        self.regenerate_token()

    def invalidate(self) -> None:
        self.data = {"_flash": {"old": [], "new": []}}
        self.regenerate(destroy=True)
