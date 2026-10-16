"""Database (T-30..T-36). See `docs/plan/LARAVEL-MAP.md` §3 for the exact export list."""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from aso.database.builder import Builder, RelationBuilder
from aso.database.db import DB, QueryExecuted
from aso.database.factory import Factory
from aso.database.model import HasUlids, HasUuids, Model, SoftDeletes, scope
from aso.database.relationships import belongs_to, belongs_to_many, has_many, has_one
from aso.database.seeder import Seeder
from aso.database.types import Encrypted, Hashed
from aso.exceptions.types import (
    LazyLoadingViolation,
    MassAssignmentError,
    ModelNotFound,
    MultipleRecordsFound,
)

__all__ = [
    "DB",
    "Builder",
    "Encrypted",
    "Factory",
    "HasUlids",
    "HasUuids",
    "Hashed",
    "LazyLoadingViolation",
    "Mapped",
    "MassAssignmentError",
    "Model",
    "ModelNotFound",
    "MultipleRecordsFound",
    "QueryExecuted",
    "RelationBuilder",
    "Seeder",
    "SoftDeletes",
    "belongs_to",
    "belongs_to_many",
    "has_many",
    "has_one",
    "mapped_column",
    "scope",
]
