"""Shared dual-repository policy: PostgreSQL authoritative when configured."""

from storage.db import is_database_configured


def postgres_authoritative() -> bool:
    return is_database_configured()
