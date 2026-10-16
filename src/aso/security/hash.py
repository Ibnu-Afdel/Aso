"""Password hashing (T-40): `hash.make`, `hash.check`, `hash.needs_rehash` (pwdlib, Argon2id).

Synchronous, like Laravel's `Hash` facade. Every framework code path that hashes during a
request (`auth().attempt()`, etc.) runs this in a worker thread with `asyncio.to_thread`; do the
same in your own async hot paths.
"""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_password_hash: PasswordHash | None = None


def _hasher() -> PasswordHash:
    global _password_hash
    if _password_hash is None:
        from aso.config import config

        options = config("hashing.argon2") or {}
        argon2 = Argon2Hasher(
            memory_cost=int(options.get("memory_cost", 65536)),
            time_cost=int(options.get("time_cost", 4)),
            parallelism=int(options.get("parallelism", 1)),
        )
        _password_hash = PasswordHash((argon2,))
    return _password_hash


def _reset_cache() -> None:
    """Testing helper: forget the cached hasher so a changed `config/hashing.py` takes effect."""
    global _password_hash
    _password_hash = None


def make(value: str) -> str:
    """Hash `value` with the configured Argon2id settings."""
    return _hasher().hash(value)


def check(value: str, hashed: str) -> bool:
    """Whether the plaintext `value` matches `hashed`. Never raises on a malformed hash."""
    if not hashed:
        return False
    try:
        return _hasher().verify(value, hashed)
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    """Whether `hashed` was produced with cost factors older than the current configuration."""
    hasher = _hasher().current_hasher
    return bool(hasher.check_needs_rehash(hashed))
