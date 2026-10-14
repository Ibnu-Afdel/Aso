"""`APP_KEY` parsing and purpose-specific key derivation (T-40).

`APP_KEY` is `base64:<32 random bytes>`. We never use those 32 bytes directly for more than one
purpose: each consumer (session cookie encryption, `crypt`, signed URLs, the session id cookie
signature) derives its own key with HKDF-SHA256 and a fixed `info` label, so a leak in one
derived key does not compromise the others.
"""

from __future__ import annotations

import base64
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_PREFIX = "base64:"


def generate_key() -> str:
    """A fresh `APP_KEY` value (`fastogram key:generate`): `base64:` + 32 random bytes."""
    return KEY_PREFIX + base64.b64encode(secrets.token_bytes(32)).decode()


def parse_app_key(raw: str) -> bytes:
    """`"base64:<32 bytes>"` -> the raw bytes. Accepts a bare base64 string too.

    `generate_key()` always produces exactly 32 bytes, but the decoded bytes are only ever fed
    into HKDF as key material (never used directly as an AES key), so any non-empty key works --
    this does not re-check the length the way Laravel's `Encrypter::supported()` does.
    """
    if not raw:
        raise RuntimeError("No application encryption key has been specified. Run `fastogram key:generate`.")
    value = raw[len(KEY_PREFIX) :] if raw.startswith(KEY_PREFIX) else raw
    try:
        key = base64.b64decode(value, validate=True)
    except Exception as exc:  # noqa: BLE001 - re-raised with a clearer message
        raise RuntimeError(f"APP_KEY is not valid base64: {raw!r}.") from exc
    if not key:
        raise RuntimeError("APP_KEY decodes to zero bytes.")
    return key


def app_key() -> bytes:
    """The current `APP_KEY`, decoded, via `config("app.key")`."""
    from fastogram.config import config

    return parse_app_key(config("app.key") or "")


def previous_app_keys() -> list[bytes]:
    """`APP_PREVIOUS_KEYS` (comma-separated, env only, like Laravel): decoded, in order."""
    from fastogram.config import env

    raw = env("APP_PREVIOUS_KEYS", "") or ""
    return [parse_app_key(k.strip()) for k in raw.split(",") if k.strip()]


def derive_key(key: bytes, info: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 derive a `length`-byte key from a 32-byte `APP_KEY` for one `info` purpose."""
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info).derive(key)


def fernet_key(key: bytes, info: bytes) -> bytes:
    """A Fernet key (32 derived bytes, URL-safe base64) for one purpose."""
    return base64.urlsafe_b64encode(derive_key(key, info))
