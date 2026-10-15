"""Inertia configuration (T-16, T-17)."""

from fastogram.config import env

# Flash the *first* error per field (Laravel's default). Set True to flash every message.
all_errors = env("INERTIA_ALL_ERRORS", False)

# Encrypt the history state for every response (T-16). Pages can also opt in individually with
# `inertia(...).encrypt_history()`.
encrypt_history = env("INERTIA_ENCRYPT_HISTORY", False)
