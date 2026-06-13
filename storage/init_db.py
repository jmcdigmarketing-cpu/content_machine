"""
Create database tables. Run once after PostgreSQL is up.

Preferred for production schema management:

    alembic upgrade head

Dev fallback (create_all, no revision tracking):

    py -m storage.init_db

Existing databases created before Alembic: verify tables, then stamp baseline:

    alembic stamp 0001
"""

from storage.db import check_database_connection, get_engine, is_database_configured
from storage.models import Base


def main():
    if not is_database_configured():
        print("DATABASE_URL is not set in .env")
        return 1

    ok, detail = check_database_connection()
    if not ok:
        print(f"Database connection failed: {detail}")
        return 1

    Base.metadata.create_all(bind=get_engine())
    print(
        "Tables created/verified: topic_scores, performance_entries, "
        "content_runs, publish_log, jobs, assets, thumbnail_scores."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
