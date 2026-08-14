"""Foreign keys from publish_log / jobs / assets / thumbnail_scores -> content_runs.

Revision ID: 0004
Revises: 0003

The `content_run_id` columns existed as bare integers with no referential integrity,
so nothing downstream could trust a run<->outcome join.

The blocker was `publish_log`: rows imported from YouTube analytics
(`analytics/seed_tapin.py`) legitimately have no originating run and recorded that as
the sentinel `0`, which is not a real run id. On the dev database 836 of 870 rows were
in that state. They carry real metrics and video ids and feed the learning loop, so
they are preserved -- the sentinel becomes NULL, which is what SQL means by "no
associated run" and what a foreign key ignores.

Follows the defensive style of 0002/0003: inspect first, return early if already
applied, so it is safe on a database that was patched by hand via
`storage/migrate_schema.py`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# table -> (constraint name, ON DELETE action)
_FKS = (
    ("publish_log", "fk_publish_log_content_run", "SET NULL"),
    ("jobs", "fk_jobs_content_run", "SET NULL"),
    ("assets", "fk_assets_content_run", "SET NULL"),
    ("thumbnail_scores", "fk_thumbnail_scores_content_run", "CASCADE"),
)


def _existing(inspector, table: str) -> set[str]:
    try:
        return {fk.get("name") for fk in inspector.get_foreign_keys(table)}
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "publish_log" in tables:
        cols = {c["name"]: c for c in inspector.get_columns("publish_log")}
        col = cols.get("content_run_id")
        # Must be nullable before the sentinel can become NULL.
        if col is not None and not col.get("nullable", False):
            op.alter_column(
                "publish_log", "content_run_id", existing_type=sa.Integer(), nullable=True
            )
        # 0 is not a real content_runs.id -- normalise before adding the constraint.
        op.execute("UPDATE publish_log SET content_run_id = NULL WHERE content_run_id = 0")

    # Defensive: any other table could carry the same sentinel or a dangling id.
    for table, _name, _ondelete in _FKS:
        if table == "publish_log" or table not in tables:
            continue
        op.execute(f"UPDATE {table} SET content_run_id = NULL WHERE content_run_id = 0")

    for table, name, ondelete in _FKS:
        if table not in tables or name in _existing(inspector, table):
            continue
        # CASCADE targets are NOT NULL, so a dangling id would fail the constraint
        # rather than being nulled out; clear those rows first.
        if ondelete == "CASCADE":
            op.execute(
                f"DELETE FROM {table} WHERE content_run_id IS NOT NULL "
                f"AND content_run_id NOT IN (SELECT id FROM content_runs)"
            )
        op.create_foreign_key(
            name, table, "content_runs", ["content_run_id"], ["id"], ondelete=ondelete
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    for table, name, _ondelete in _FKS:
        if table in tables and name in _existing(inspector, table):
            op.drop_constraint(name, table, type_="foreignkey")

    # Restore the legacy sentinel so the pre-0004 NOT NULL can be reinstated.
    if "publish_log" in tables:
        op.execute("UPDATE publish_log SET content_run_id = 0 WHERE content_run_id IS NULL")
        op.alter_column(
            "publish_log", "content_run_id", existing_type=sa.Integer(), nullable=False
        )
