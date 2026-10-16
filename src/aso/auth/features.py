"""`features.enabled(name)` (T-38): toggle built-in auth flows via `config("auth.features")`."""

from __future__ import annotations

__all__ = ["features"]


class _Features:
    def enabled(self, name: str) -> bool:
        from aso.config import config

        return name in (config("auth.features") or [])


features = _Features()
