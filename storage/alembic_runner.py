"""
Programmatic Alembic helpers for scripts and tests.

Production: prefer ``alembic upgrade head`` with DATABASE_URL set.
``py -m storage.init_db`` remains a dev fallback (create_all).
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from config.settings import get_settings
from storage.db import is_database_configured

_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    url = get_settings().database_url
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def current_revision() -> str | None:
    """Head revision id from the script directory (no DB connection)."""
    script = ScriptDirectory.from_config(_alembic_config())
    head = script.get_current_head()
    return head


def upgrade_head() -> None:
    """Run all pending migrations. Requires DATABASE_URL."""
    if not is_database_configured():
        raise RuntimeError("DATABASE_URL is not set")
    command.upgrade(_alembic_config(), "head")


def maybe_auto_upgrade() -> bool:
    """
    Upgrade when ALEMBIC_AUTO_UPGRADE is enabled. Returns True if upgrade ran.
    """
    if os.getenv("ALEMBIC_AUTO_UPGRADE", "").lower() not in ("1", "true", "yes"):
        return False
    if not is_database_configured():
        return False
    upgrade_head()
    return True
