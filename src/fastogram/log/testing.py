"""`LogCapture` (T-22): intercept log records in tests.

```python
with LogCapture() as logs:
    log.info("Processing order", order_id=42)

assert logs.has("Processing order")
assert logs.records[0]["order_id"] == 42
```

Attaches to the `"fastogram"` logger, the common ancestor of every `fastogram.channel.*` logger,
so it captures a call regardless of which channel it went to (and independently of whatever real
sinks `configure_logging()` installed). `fastogram.testing` should re-export this name (see the
report: that module is owned by a different package task).
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["LogCapture"]


class _CaptureHandler(logging.Handler):
    def __init__(self, records: list[dict[str, Any]]) -> None:
        super().__init__()
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        context: dict[str, Any] = getattr(record, "context", None) or {}
        self._records.append(
            {
                "level": record.levelname,
                "channel": record.name.removeprefix("fastogram.channel."),
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", None),
                **context,
            }
        )


class LogCapture:
    """A context manager that records every log call made while it is open."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._handler = _CaptureHandler(self.records)
        self._logger = logging.getLogger("fastogram")

    def __enter__(self) -> LogCapture:
        self._logger.addHandler(self._handler)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._logger.removeHandler(self._handler)

    def has(self, message: str) -> bool:
        return any(message in r["message"] for r in self.records)
