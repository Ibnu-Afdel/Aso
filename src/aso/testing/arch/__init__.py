"""Architecture tests (T-58): `arch()`, `arch_preset()`, `ArchitectureViolation`.

Reads code with Python's `ast` module -- never a text search -- so comments, strings and
aliased imports never cause false alarms or false negatives.
"""

from __future__ import annotations

from aso.testing.arch._preset import arch_preset
from aso.testing.arch._selection import ArchitectureViolation, arch

__all__ = ["ArchitectureViolation", "arch", "arch_preset"]
