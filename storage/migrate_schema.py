"""
Incremental schema updates for existing PostgreSQL databases.

create_all in init_db does not alter existing tables. For new installs prefer:

    alembic upgrade head

Legacy incremental patches (idempotency_key, assets, content_runs columns):

    py -m storage.migrate_schema

After Alembic is adopted, stamp baseline on DBs that already have tables:

    alembic stamp 0001
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from storage.db import check_database_connection, get_engine, is_database_configured
from storage.models import Asset, ThumbnailScore


def main() -> int:
    if not is_database_configured():
        print("DATABASE_URL is not set in .env")
        return 1

    ok, detail = check_database_connection()
    if not ok:
        print(f"Database connection failed: {detail}")
        return 1

    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "publish_log" in tables:
            cols = {c["name"] for c in inspector.get_columns("publish_log")}
            if "idempotency_key" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE publish_log "
                        "ADD COLUMN idempotency_key VARCHAR(128) DEFAULT ''"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_publish_log_idempotency_key "
                        "ON publish_log (idempotency_key)"
                    )
                )
                print("Added publish_log.idempotency_key")
            else:
                print("publish_log.idempotency_key already present")

            conn.execute(
                text(
                    """
                    DELETE FROM publish_log a
                    USING publish_log b
                    WHERE a.idempotency_key = b.idempotency_key
                      AND a.idempotency_key <> ''
                      AND a.id > b.id
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_publish_log_idempotency_key
                    ON publish_log (idempotency_key)
                    WHERE (idempotency_key <> '')
                    """
                )
            )
            print("Ensured unique idempotency_key (partial index)")
        else:
            print("publish_log table missing — run py -m storage.init_db first")

        if "assets" not in tables:
            Asset.__table__.create(bind=conn, checkfirst=True)
            print("Created assets table")
        else:
            print("assets table already exists")

        if "thumbnail_scores" not in tables:
            ThumbnailScore.__table__.create(bind=conn, checkfirst=True)
            print("Created thumbnail_scores table")
        else:
            print("thumbnail_scores table already exists")

        if "content_runs" in tables:
            cr_cols = {c["name"] for c in inspector.get_columns("content_runs")}
            for col, ddl in (
                ("tags_json", "ALTER TABLE content_runs ADD COLUMN tags_json TEXT DEFAULT '[]'"),
                (
                    "brief_version",
                    "ALTER TABLE content_runs ADD COLUMN brief_version VARCHAR(64) DEFAULT ''",
                ),
                (
                    "prompt_version",
                    "ALTER TABLE content_runs ADD COLUMN prompt_version VARCHAR(64) DEFAULT ''",
                ),
            ):
                if col not in cr_cols:
                    conn.execute(text(ddl))
                    print(f"Added content_runs.{col}")
                else:
                    print(f"content_runs.{col} already present")
        else:
            print("content_runs table missing — run py -m storage.init_db first")

    print("Schema migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
