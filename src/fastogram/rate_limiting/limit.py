"""`Limit`: what a `RateLimiter.for_()` callback returns (T-44)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Limit:
    """`Limit.per_minute(60).by(user_id)`. `unlimited` is `Limit.none()`: never throttle."""

    max_attempts: int
    decay_minutes: float = 1.0
    key: str | None = None
    unlimited: bool = False

    @classmethod
    def per_minute(cls, max_attempts: int) -> Limit:
        return cls(max_attempts, 1.0)

    @classmethod
    def per_hour(cls, max_attempts: int) -> Limit:
        return cls(max_attempts, 60.0)

    @classmethod
    def per_day(cls, max_attempts: int) -> Limit:
        return cls(max_attempts, 1440.0)

    @classmethod
    def none(cls) -> Limit:
        return cls(0, 0.0, unlimited=True)

    def by(self, key: Any) -> Limit:
        self.key = str(key)
        return self

    @property
    def decay_seconds(self) -> int:
        return int(self.decay_minutes * 60)
