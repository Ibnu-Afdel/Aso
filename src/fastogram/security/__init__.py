"""Hashing and encryption (T-40): `from fastogram.security import hash, crypt, DecryptException`."""

from __future__ import annotations

from fastogram.exceptions.types import DecryptException
from fastogram.security import crypt, hash
from fastogram.security.keys import generate_key, parse_app_key

__all__ = ["DecryptException", "crypt", "generate_key", "hash", "parse_app_key"]
