"""Two-way authenticated encryption (T-40): `crypt.encrypt`, `crypt.decrypt`, `crypt.rotate`.

`cryptography`'s `Fernet` (AES-128-CBC + HMAC-SHA256, with a timestamp) under `MultiFernet`:
`crypt.encrypt` always uses the primary key (derived from `APP_KEY`); `crypt.decrypt` and
`crypt.rotate` also try each `APP_PREVIOUS_KEYS` entry, in order, so a key rotation does not
immediately invalidate existing encrypted values.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from fastogram.exceptions.types import DecryptException
from fastogram.security.keys import app_key, fernet_key, previous_app_keys

PURPOSE = b"fastogram-encryption"


def _multi_fernet() -> MultiFernet:
    keys = [app_key(), *previous_app_keys()]
    return MultiFernet([Fernet(fernet_key(k, PURPOSE)) for k in keys])


def encrypt(value: str | bytes) -> str:
    """Encrypt `value` with the primary key. Returns a URL-safe base64 token."""
    data = value.encode() if isinstance(value, str) else value
    return _multi_fernet().encrypt(data).decode()


def encrypt_string(value: str) -> str:
    return encrypt(value)


def decrypt(token: str | bytes) -> str:
    """Decrypt `token`, trying the primary key then each `APP_PREVIOUS_KEYS` entry.

    Raises `DecryptException` if the token is invalid, tampered with, or was encrypted with a
    key this app no longer has.
    """
    data = token.encode() if isinstance(token, str) else token
    try:
        return _multi_fernet().decrypt(data).decode()
    except InvalidToken as exc:
        raise DecryptException("The payload is invalid.") from exc


def decrypt_string(token: str) -> str:
    return decrypt(token)


def rotate(token: str | bytes) -> str:
    """Re-encrypt `token` with the primary key (`MultiFernet.rotate`), for key-rotation scripts."""
    data = token.encode() if isinstance(token, str) else token
    try:
        return _multi_fernet().rotate(data).decode()
    except InvalidToken as exc:
        raise DecryptException("The payload is invalid.") from exc
