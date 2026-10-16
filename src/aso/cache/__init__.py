"""Cache (T-44): `cache()` / `cache(store)`.

```python
from aso.cache import cache

await cache().remember("system.stats", 600, fetch_fresh_stats)
```

Stores: `memory` (process dict, TTL), `file` (`storage/framework/cache/`, atomic writes),
`redis` (`redis.asyncio`, needs the optional `redis` package). Configure in `config/cache.py`;
sensible defaults apply when that file is missing (see `manager._store_spec`).
"""

from __future__ import annotations

from aso.cache.manager import CacheStore, cache, flush_all

__all__ = ["CacheStore", "cache", "flush_all"]
