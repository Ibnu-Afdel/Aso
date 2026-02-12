from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class _ScopeState:
    depth: int = 0
    commit_requested: bool = False


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
        self._scope_state: ContextVar[_ScopeState | None] = ContextVar(
            "scope_state",
            default=None,
        )

    @asynccontextmanager
    async def session_scope(self, commit_on_exit: bool = False):
        existing_session = self._current_session.get()
        existing_state = self._scope_state.get()
        if existing_session is not None and existing_state is not None:
            existing_state.depth += 1
            if commit_on_exit:
                existing_state.commit_requested = True
            try:
                yield existing_session
            finally:
                existing_state.depth -= 1
            return

        session = self._session_factory()
        token: Token[AsyncSession | None] = self._current_session.set(session)
        state = _ScopeState(depth=1, commit_requested=commit_on_exit)
        state_token: Token[_ScopeState | None] = self._scope_state.set(state)
        try:
            yield session
            if state.commit_requested or self._commit_on_exit:
                await session.commit()
            else:
                await session.rollback()
        except Exception:
            await session.rollback()
            raise
        finally:
            self._current_session.reset(token)
            self._scope_state.reset(state_token)
            await session.close()

    def get_session(self) -> AsyncSession:
        session = self._current_session.get()
        if session is None:
            raise RuntimeError(
                "No active DB session in context. Wrap execution in SessionManager.session_scope()."
            )
        return session
