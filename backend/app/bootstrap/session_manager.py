from contextlib import asynccontextmanager
from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SessionManager:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        commit_on_exit: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._commit_on_exit = commit_on_exit
        self._current_session: ContextVar[AsyncSession | None] = ContextVar(
            "current_session",
            default=None,
        )

    @asynccontextmanager
    async def session_scope(self):
        existing_session = self._current_session.get()
        if existing_session is not None:
            yield existing_session
            return

        session = self._session_factory()
        token: Token[AsyncSession | None] = self._current_session.set(session)
        try:
            yield session
            if self._commit_on_exit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            self._current_session.reset(token)
            await session.close()

    def get_session(self) -> AsyncSession:
        session = self._current_session.get()
        if session is None:
            raise RuntimeError(
                "No active DB session in context. Wrap execution in SessionManager.session_scope()."
            )
        return session
