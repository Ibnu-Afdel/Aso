"""String helpers named in the guide pages (currently just `slug`, used by `config/session.py`).

Port of Laravel's `Illuminate\\Support\\Str::slug()`: ASCII-transliterate, lowercase, replace
runs of anything that is not a letter/digit/separator with nothing, then collapse whitespace and
separators into a single separator and trim it from both ends.
"""

from __future__ import annotations

import re
import unicodedata

_DEFAULT_DICTIONARY = {"@": "at"}


def slug(value: str, separator: str = "-", dictionary: dict[str, str] | None = None) -> str:
    """`slug("Aso's App")` -> `"asos-app"`. `slug("Bjørn & Co", "_")` -> `"bjorn_and_co"`."""
    merged = {**_DEFAULT_DICTIONARY, **(dictionary or {})}

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")

    for search, replace in merged.items():
        ascii_value = ascii_value.replace(search, f"{separator}{replace}{separator}")

    ascii_value = ascii_value.lower()
    escaped = re.escape(separator)
    ascii_value = re.sub(rf"[^{escaped}a-z0-9\s]+", "", ascii_value)
    ascii_value = re.sub(rf"[{escaped}\s]+", separator, ascii_value)
    return ascii_value.strip(separator)
