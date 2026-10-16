"""The async engine, built from `config("database")` (T-30).

URL building for sqlite/pgsql/mysql (including `sslmode` → asyncpg `ssl`), the SQLite
transaction recipe (S-2) and PRAGMAs, pool sizing, and the `before/after_cursor_execute` query
listener that feeds `DB.listen()`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

_engine: AsyncEngine | None = None
_maker: async_sessionmaker[AsyncSession] | None = None

_SSLMODE_TO_SSL = {
    "disable": "false",
    "allow": None,
    "prefer": None,
    "require": "true",
    "verify-ca": "true",
    "verify-full": "true",
}


def _rewrite_sslmode(url: str) -> str:
    """`?sslmode=require` (libpq) → `?ssl=true` (asyncpg's connect kwarg)."""
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query))
    sslmode = params.pop("sslmode", None)
    ssl_value = _SSLMODE_TO_SSL.get(sslmode) if sslmode else None
    if ssl_value is not None:
        params["ssl"] = ssl_value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))

ASYNC_DRIVERS = {
    "sqlite": "sqlite+aiosqlite",
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
    "pgsql": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "mariadb": "mysql+asyncmy",
}


def database_url(connection: dict[str, Any], base_path: Path | None = None) -> str:
    """Build an async SQLAlchemy URL from one `config/database.py` connection.

    A plain `DB_URL` (`postgresql://`, `postgres://`, `mysql://`) is rewritten to the async
    driver. `?sslmode=` is translated to asyncpg's `ssl` connect argument (T-30).
    """
    url = connection.get("url")
    if url:
        scheme, _, rest = str(url).partition("://")
        driver = ASYNC_DRIVERS.get(scheme.split("+")[0], scheme)
        rewritten = f"{driver}://{rest}"
        if driver == "postgresql+asyncpg" and "sslmode=" in rewritten:
            rewritten = _rewrite_sslmode(rewritten)
        return rewritten
    driver = connection.get("driver", "sqlite")
    if driver == "sqlite":
        database = str(connection.get("database") or ":memory:")
        if database == ":memory:":
            return "sqlite+aiosqlite://"
        path = Path(database)
        if not path.is_absolute() and base_path is not None:
            path = base_path / path
        return f"sqlite+aiosqlite:///{path}"
    scheme = ASYNC_DRIVERS[driver]
    user = connection.get("username") or ""
    password = connection.get("password") or ""
    auth = f"{user}:{password}@" if password else (f"{user}@" if user else "")
    host = connection.get("host", "127.0.0.1")
    port = connection.get("port")
    db = connection.get("database", "")
    url = f"{scheme}://{auth}{host}{f':{port}' if port else ''}/{db}"
    sslmode = connection.get("sslmode")
    if scheme == "postgresql+asyncpg" and sslmode:
        url = _rewrite_sslmode(f"{url}?sslmode={sslmode}")
    return url


def install_sqlite_recipe(engine: AsyncEngine, pragmas: dict[str, Any] | None = None) -> None:
    """S-2 finding: aiosqlite does not emit BEGIN, so SAVEPOINT/RELEASE would commit for real.

    Take over transaction control (SQLAlchemy's pysqlite recipe) and set the PRAGMAs on connect.
    """
    pragmas = pragmas or {}

    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        if pragmas.get("foreign_keys", True):
            cursor.execute("PRAGMA foreign_keys=ON")
        if pragmas.get("busy_timeout"):
            cursor.execute(f"PRAGMA busy_timeout={int(pragmas['busy_timeout'])}")
        if pragmas.get("journal_mode"):
            cursor.execute(f"PRAGMA journal_mode={pragmas['journal_mode']}")
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN")


def install_query_listener(engine: AsyncEngine, connection_name: str | None = None) -> None:
    """`before/after_cursor_execute` on `engine.sync_engine` → `DB.listen()` (T-30)."""
    from aso.database.db import QueryExecuted, notify

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: bool) -> None:
        conn.info.setdefault("aso_query_start", []).append(time.perf_counter())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: bool) -> None:
        stack = conn.info.get("aso_query_start") or []
        started = stack.pop() if stack else time.perf_counter()
        elapsed_ms = (time.perf_counter() - started) * 1000
        bindings = parameters if isinstance(parameters, dict) else {}
        notify(QueryExecuted(sql=str(statement), bindings=dict(bindings), time_ms=elapsed_ms, connection_name=connection_name))


def make_engine(url: str, connection: dict[str, Any] | None = None, *, name: str | None = None, **kwargs: Any) -> AsyncEngine:
    connection = connection or {}
    sa_url = make_url(url)
    pool = _pool_kwargs(connection)
    if sa_url.get_backend_name() == "sqlite":
        if sa_url.database in (None, "", ":memory:"):
            kwargs.setdefault("poolclass", StaticPool)
            kwargs.setdefault("connect_args", {"check_same_thread": False})
        else:
            kwargs.update(pool)
        engine = create_async_engine(sa_url, **kwargs)
        install_sqlite_recipe(
            engine,
            {
                # T-30: foreign keys, a 5 s busy timeout and WAL are on by default. Without WAL, the
                # request's open read transaction blocks the session driver's own write connection.
                "foreign_keys": connection.get("foreign_key_constraints", True),
                "busy_timeout": connection.get("busy_timeout", 5000),
                "journal_mode": connection.get("journal_mode", "wal") if sa_url.database not in (None, "", ":memory:") else None,
            },
        )
    else:
        kwargs.setdefault("pool_pre_ping", True)
        kwargs.update(pool)
        engine = create_async_engine(sa_url, **kwargs)
    install_query_listener(engine, name)
    return engine


def _pool_kwargs(connection: dict[str, Any]) -> dict[str, Any]:
    from aso.config import config

    size = connection.get("pool_size", config("database.pool.size"))
    overflow = connection.get("pool_max_overflow", config("database.pool.max_overflow"))
    kwargs: dict[str, Any] = {}
    if size is not None:
        kwargs["pool_size"] = int(size)
    if overflow is not None:
        kwargs["max_overflow"] = int(overflow)
    return kwargs


def configure(engine: AsyncEngine) -> None:
    global _engine, _maker
    _engine = engine
    _maker = async_sessionmaker(engine, expire_on_commit=False)


def configure_from_config() -> AsyncEngine | None:
    from aso.config import config
    from aso.foundation.paths import base_path

    name = config("database.default")
    if not name:
        return None
    connection = config(f"database.connections.{name}") or {}
    engine = make_engine(database_url(connection, base_path()), connection, name=name)
    configure(engine)
    if config("database.log_queries"):
        _install_default_logger()
    return engine


def _install_default_logger() -> None:
    import logging

    from aso.database.db import DB

    logger = logging.getLogger("aso.database.query")
    DB.listen(lambda q: logger.debug("sql=%s bindings=%s ms=%.2f", q.sql, q.bindings, q.time_ms))


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("The database is not configured. Is config/database.py present?")
    return _engine


def session_maker() -> async_sessionmaker[AsyncSession]:
    if _maker is None:
        raise RuntimeError("The database is not configured. Is config/database.py present?")
    return _maker


async def dispose() -> None:
    if _engine is not None:
        await _engine.dispose()
