"""Worker restart signal (T-42): `run_worker()` stops once `queue:restart` has written a
newer timestamp than the worker's own start time (`aso:queue:restart` in `aso.cache`,
D-011's cache-signal approach, see the build report for why this is checked in-process rather
than against a live broker)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aso.queue.worker import RESTART_SIGNAL_KEY, _restart_requested


async def test_no_signal_means_no_restart():
    assert await _restart_requested(datetime.now(UTC)) is False


async def test_signal_older_than_start_is_ignored():
    from aso.cache import cache

    started_at = datetime.now(UTC)
    await cache().put(RESTART_SIGNAL_KEY, (started_at - timedelta(seconds=5)).isoformat())
    assert await _restart_requested(started_at) is False


async def test_signal_newer_than_start_requests_a_restart():
    from aso.cache import cache

    started_at = datetime.now(UTC)
    await cache().put(RESTART_SIGNAL_KEY, (started_at + timedelta(seconds=5)).isoformat())
    assert await _restart_requested(started_at) is True
