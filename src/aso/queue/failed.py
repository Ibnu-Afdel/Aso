"""The `failed_jobs` table (T-42): `record_failed_job`, and the functions the CLI's
`queue:failed/retry/forget/flush` tasks will call.

Plain SQL through `DB` (no `Model`/ORM mapping), so this table exists independently of the app's
own `Model` registry and migrations -- a framework table, created on first use with
`CREATE TABLE IF NOT EXISTS`, like Laravel's `queue:failed-table` migration but automatic.
"""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aso.database.db import DB

TABLE = "failed_jobs"


async def _ensure_table() -> None:
    """`CREATE TABLE IF NOT EXISTS`, every call: cheap, idempotent, and safe across engines
    (caching by engine identity is not, since a disposed engine's `id()` can be reused)."""
    from aso.database.engine import engine

    eng = engine()
    dialect = eng.dialect.name
    if dialect == "postgresql":
        id_column = "id BIGSERIAL PRIMARY KEY"
    elif dialect in ("mysql", "mariadb"):
        id_column = "id BIGINT PRIMARY KEY AUTO_INCREMENT"
    else:
        id_column = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    await DB.statement(
        f"""CREATE TABLE IF NOT EXISTS {TABLE} (
            {id_column},
            uuid VARCHAR(36) NOT NULL,
            connection VARCHAR(255) NOT NULL,
            queue VARCHAR(255) NOT NULL,
            payload TEXT NOT NULL,
            exception TEXT NOT NULL,
            failed_at VARCHAR(40) NOT NULL
        )"""
    )


async def record_failed_job(payload: dict[str, Any], exc: BaseException, connection: str | None = None) -> None:
    await _ensure_table()
    await DB.insert(
        f"INSERT INTO {TABLE} (uuid, connection, queue, payload, exception, failed_at) "
        "VALUES (:uuid, :connection, :queue, :payload, :exception, :failed_at)",
        {
            "uuid": payload.get("uuid") or str(uuid4()),
            "connection": connection or payload.get("connection") or "sync",
            "queue": payload.get("queue", "default"),
            "payload": json.dumps(payload),
            "exception": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "failed_at": datetime.now(UTC).isoformat(),
        },
    )


async def list_failed() -> list[dict[str, Any]]:
    await _ensure_table()
    return await DB.select(f"SELECT * FROM {TABLE} ORDER BY id")


async def retry_failed(id_or_all: int | str) -> int:
    """Re-dispatch one failed job (by id) or every one (`"all"`). Returns the number retried."""
    await _ensure_table()
    if id_or_all == "all":
        rows = await list_failed()
    else:
        row = await DB.select_one(f"SELECT * FROM {TABLE} WHERE id = :id", {"id": int(id_or_all)})
        rows = [row] if row else []

    from aso.queue import drivers
    from aso.queue.manager import enqueue_payload

    count = 0
    for row in rows:
        payload = json.loads(row["payload"])
        payload["attempt"] = 1
        spec = drivers.connection_spec(payload.get("connection"))
        await enqueue_payload(spec, payload)
        await forget_failed(row["id"])
        count += 1
    return count


async def forget_failed(id_: int) -> bool:
    await _ensure_table()
    affected = await DB.delete(f"DELETE FROM {TABLE} WHERE id = :id", {"id": int(id_)})
    return affected > 0


async def flush_failed() -> int:
    await _ensure_table()
    return await DB.delete(f"DELETE FROM {TABLE}", {})
