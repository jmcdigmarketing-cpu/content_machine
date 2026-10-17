import os
from collections.abc import Mapping
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def suite_database_refusal(url: str, environ: Mapping[str, str] | None = None) -> str:
    """Why ``url`` may not be opened, or "" (#1247).

    While the test suite runs (`CONTENT_SUITE=1`, set by tests/__init__.py) only a temporary
    SQLite file or CI's own `CONTENT_TEST_DATABASE_URL` is opened - never the operator's
    Postgres, even when `Settings.database_url` was frozen before the suite could blank it.
    """
    env = os.environ if environ is None else environ
    if str(env.get("CONTENT_SUITE") or "") != "1" or not url:
        return ""
    if url.startswith("sqlite"):
        return ""
    if url == str(env.get("CONTENT_TEST_DATABASE_URL") or "").strip():
        return ""
    return "the test suite does not open a real database (#1247)"


def is_database_configured() -> bool:
    url = get_settings().database_url
    return bool(url) and not suite_database_refusal(url)


@lru_cache
def get_engine() -> Engine:
    global _engine, _SessionLocal
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set in .env")
    refused = suite_database_refusal(url)
    if refused:
        raise RuntimeError(refused)
    _engine = create_engine(url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal()


def check_database_connection():
    if not is_database_configured():
        return False, "DATABASE_URL not set"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connected"
    except Exception as e:
        return False, str(e)[:120]
