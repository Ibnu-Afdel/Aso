"""File storage (T-43): `storage(disk)` / `storage()`.

```python
from fastogram.storage import storage

await storage("local").put("reports/x.txt", data)
storage("public").url("avatars/1.jpg")
```

Disks `local` (`storage/app`) and `public` (`storage/app/public`, served at `/storage/...`).
Configure in `config/filesystems.py`; sensible defaults apply when that file is missing.
`storage.fake(disk)` swaps a disk for a temp directory in tests.
"""

from __future__ import annotations

from fastogram.storage.manager import Disk, link_public_storage, storage

__all__ = ["Disk", "link_public_storage", "storage"]
