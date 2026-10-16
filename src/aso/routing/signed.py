"""Signed URLs and the `signed` route-middleware alias (T-21).

HMAC-SHA256 over the URL (minus `signature`), with a key derived from `APP_KEY` via PBKDF2-HMAC
(a purpose-specific derivation, so this differs from the session and encryption keys, T-18/T-40).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from starlette.types import ASGIApp, Receive, Scope, Send

from aso.exceptions.types import InvalidSignatureException

_INFO = b"aso-url-signature"


def _signing_key() -> bytes:
    from aso.config import config

    raw = str(config("app.key") or "")
    material = raw.removeprefix("base64:")
    try:
        key_bytes = base64.b64decode(material) if raw.startswith("base64:") else raw.encode()
    except Exception:
        key_bytes = raw.encode()
    return hashlib.pbkdf2_hmac("sha256", key_bytes, _INFO, 1, dklen=32)


def _hmac_for(url_without_signature: str) -> str:
    return hmac.new(_signing_key(), url_without_signature.encode(), hashlib.sha256).hexdigest()


def sign_url(url: str, params: dict[str, Any] | None = None, expires: int | None = None) -> str:
    """Append `expires` (optional) and `signature` query parameters to `url`."""
    scheme, netloc, path, query, _fragment = urlsplit(url)
    q: dict[str, str] = dict(parse_qsl(query, keep_blank_values=True))
    if params:
        q.update({k: str(v) for k, v in params.items()})
    if expires is not None:
        q["expires"] = str(int(expires))
    base = urlunsplit((scheme, netloc, path, urlencode(q), ""))
    q["signature"] = _hmac_for(base)
    return urlunsplit((scheme, netloc, path, urlencode(q), ""))


def verify_url(url: str) -> bool:
    """Recompute the signature over `url` (minus `signature`) and check `expires`.

    `sign_url()` signs the URL *with* `expires` already in the query string (it is added before
    `signature` is computed, see `sign_url`), so `expires` must stay in the query here too when
    rebuilding `base` -- only `signature` itself is excluded from the signed payload.
    """
    scheme, netloc, path, query, _fragment = urlsplit(url)
    q: dict[str, str] = dict(parse_qsl(query, keep_blank_values=True))
    signature = q.pop("signature", None)
    if not signature:
        return False
    base = urlunsplit((scheme, netloc, path, urlencode(q), ""))
    if not hmac.compare_digest(_hmac_for(base), signature):
        return False
    expires = q.get("expires")
    if expires is not None:
        try:
            if time.time() > float(expires):
                return False
        except ValueError:
            return False
    return True


class ValidateSignature:
    """Route-middleware alias `signed` (T-21): raises `InvalidSignatureException` (403) on a bad
    or expired signature."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from aso import context

        ctx = context.current()
        if ctx is None or ctx.request is None:
            raise RuntimeError("ValidateSignature requires an active request context.")
        if not verify_url(str(ctx.request.url)):
            raise InvalidSignatureException()
        await self.app(scope, receive, send)
