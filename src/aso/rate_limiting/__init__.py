"""Rate limiting (T-44): `RateLimiter`, `Limit`, `ThrottleRequestsException`.

```python
from aso.rate_limiting import Limit, RateLimiter

RateLimiter.for_("api", lambda request: Limit.per_minute(60).by(request.client_ip()))
```

Backed by the cache (`aso.cache`). The `throttle:` route-middleware alias lives in
`aso.rate_limiting.middleware.ThrottleRequests` (registered by
`aso.foundation.middleware_config.DEFAULT_ALIASES`).
"""

from __future__ import annotations

from aso.exceptions.types import ThrottleRequestsException
from aso.rate_limiting.limit import Limit
from aso.rate_limiting.limiter import RateLimiter

__all__ = ["Limit", "RateLimiter", "ThrottleRequestsException"]
