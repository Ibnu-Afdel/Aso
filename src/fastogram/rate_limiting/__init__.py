"""Rate limiting (T-44): `RateLimiter`, `Limit`, `ThrottleRequestsException`.

```python
from fastogram.rate_limiting import Limit, RateLimiter

RateLimiter.for_("api", lambda request: Limit.per_minute(60).by(request.client_ip()))
```

Backed by the cache (`fastogram.cache`). The `throttle:` route-middleware alias lives in
`fastogram.rate_limiting.middleware.ThrottleRequests` (registered by
`fastogram.foundation.middleware_config.DEFAULT_ALIASES`).
"""

from __future__ import annotations

from fastogram.exceptions.types import ThrottleRequestsException
from fastogram.rate_limiting.limit import Limit
from fastogram.rate_limiting.limiter import RateLimiter

__all__ = ["Limit", "RateLimiter", "ThrottleRequestsException"]
