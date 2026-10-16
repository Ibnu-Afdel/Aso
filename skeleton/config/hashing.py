"""Hashing configuration (T-40). `aso.security.hash` reads this for Argon2 tuning."""

driver = "argon2"

argon2 = {
    "memory_cost": 65536,
    "time_cost": 4,
    "parallelism": 1,
}
