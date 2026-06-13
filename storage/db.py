from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def is_database_configured() -> bool:
    return bool(get_settings().database_url)


@lru_cache
def get_engine() -> Engine:
    global _engine, _SessionLocal
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set in .env")
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
