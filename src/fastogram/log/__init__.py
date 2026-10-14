"""Logging (T-22): `log.debug/info/notice/warning/error/critical(msg, **context)`.

`from fastogram.log import log`; `log.channel("orders").warning(...)` for a specific channel.
"""

from __future__ import annotations

from fastogram.log.manager import ChannelLogger, Log, configure_logging, log

__all__ = ["ChannelLogger", "Log", "configure_logging", "log"]
