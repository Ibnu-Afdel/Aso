"""`throttle:` route middleware (T-11, T-44).

`.middleware("throttle:60,1")` (60 attempts per 1 minute) or `.middleware("throttle:api")` (a
named limiter registered with `RateLimiter.for_("api", ...)`). On excess it raises
`ThrottleRequestsException`, rendered by the exception handler (T-20) as 429 + `Retry-After`.
A successful response gets `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers.
"""

from __future__ import annotations

from typing import Any

from fastogram.exceptions.types import ThrottleRequestsException
from fastogram.http.middleware import Middleware, Next
from fastogram.rate_limiting.limit import Limit
from fastogram.rate_limiting.limiter import RateLimiter


class ThrottleRequests(Middleware):
    async def handle(self, request: Any, next: Next, *params: str) -> Any:
        limit = _resolve_limit(request, params)
        if limit is None or limit.unlimited:
            return await next(request)

        key = limit.key or _default_key(request)
        if await RateLimiter.too_many_attempts(key, limit.max_attempts):
            retry_after = await RateLimiter.available_in(key)
            raise ThrottleRequestsException(retry_after or limit.decay_seconds)

        await RateLimiter.hit(key, limit.decay_seconds)
        response = await next(request)
        remaining = await RateLimiter.remaining(key, limit.max_attempts)
        response.headers["X-RateLimit-Limit"] = str(limit.max_attempts)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def _resolve_limit(request: Any, params: tuple[str, ...]) -> Limit | None:
    if not params:
        raise RuntimeError('The "throttle" middleware needs parameters: "throttle:60,1" or "throttle:<limiter>".')
    first = params[0]
    if first.lstrip("-").isdigit():
        max_attempts = int(first)
        decay_minutes = float(params[1]) if len(params) > 1 else 1.0
        return Limit(max_attempts, decay_minutes)

    callback = RateLimiter.limiter(first)
    if callback is None:
        raise RuntimeError(
            f'The "throttle:{first}" middleware refers to a limiter that was never defined. Register '
            f'it in bootstrap/app.py with `RateLimiter.for_("{first}", lambda request: Limit.per_minute(60))`.'
        )
    result = callback(request)
    if result is None:
        return None
    limits = result if isinstance(result, (list, tuple)) else [result]
    for candidate in limits:
        if not candidate.unlimited:
            return candidate
    return limits[0] if limits else None


def _default_key(request: Any) -> str:
    """Laravel's default: the user id if logged in, else the client IP plus the route (T-44)."""
    from fastogram.auth import auth

    user_id = auth().id()
    if user_id is not None:
        return str(user_id)
    ip = request.client_ip() or "unknown"
    route = request.scope.get("route") if hasattr(request, "scope") else None
    path = getattr(route, "path", None) or request.path()
    return f"{ip}|{request.method}:{path}"
