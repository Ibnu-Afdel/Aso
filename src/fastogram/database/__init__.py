"""Database (T-30..T-36). See `docs/plan/LARAVEL-MAP.md` §3 for the exact export list."""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from fastogram.database.builder import Builder, RelationBuilder
from fastogram.database.db import DB, QueryExecuted
from fastogram.database.factory import Factory
from fastogram.database.model import HasUlids, HasUuids, Model, SoftDeletes, scope
from fastogram.database.relationships import belongs_to, belongs_to_many, has_many, has_one
from fastogram.database.seeder import Seeder
from fastogram.database.types import Encrypted, Hashed
from fastogram.exceptions.types import (
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
