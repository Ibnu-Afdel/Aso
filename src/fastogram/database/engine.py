"""The async engine, built from `config("database")` (T-30).

SEED (spine): URL building for sqlite/pgsql/mysql, the SQLite transaction recipe (S-2) and
PRAGMAs. The database package task completes pool options, sslmode, the query listener.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

_engine: AsyncEngine | None = None
_maker: async_sessionmaker[AsyncSession] | None = None

ASYNC_DRIVERS = {
    "sqlite": "sqlite+aiosqlite",
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
    "pgsql": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "mariadb": "mysql+asyncmy",
}


def database_url(connection: dict[str, Any], base_path: Path | None = None) -> str:
    """Build an async SQLAlchemy URL from one `config/database.py` connection."""
    url = connection.get("url")
    if url:
        scheme, _, rest = str(url).partition("://")
        driver = ASYNC_DRIVERS.get(scheme.split("+")[0], scheme)
        return f"{driver}://{rest}"
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
    return f"{scheme}://{auth}{host}{f':{port}' if port else ''}/{db}"


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


def make_engine(url: str, connection: dict[str, Any] | None = None, **kwargs: Any) -> AsyncEngine:
    connection = connection or {}
    sa_url = make_url(url)
    if sa_url.get_backend_name() == "sqlite":
        if sa_url.database in (None, "", ":memory:"):
            kwargs.setdefault("poolclass", StaticPool)
            kwargs.setdefault("connect_args", {"check_same_thread": False})
        engine = create_async_engine(sa_url, **kwargs)
        install_sqlite_recipe(
            engine,
            {
                "foreign_keys": connection.get("foreign_key_constraints", True),
                "busy_timeout": connection.get("busy_timeout"),
                "journal_mode": connection.get("journal_mode") if sa_url.database not in (None, "", ":memory:") else None,
            },
        )
        return engine
    kwargs.setdefault("pool_pre_ping", True)
    return create_async_engine(sa_url, **kwargs)


def configure(engine: AsyncEngine) -> None:
    global _engine, _maker
    _engine = engine
    _maker = async_sessionmaker(engine, expire_on_commit=False)


def configure_from_config() -> AsyncEngine | None:
    from fastogram.config import config
    from fastogram.foundation.paths import base_path

    name = config("database.default")
    if not name:
        return None
    connection = config(f"database.connections.{name}") or {}
    engine = make_engine(database_url(connection, base_path()), connection)
    configure(engine)
    return engine


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
