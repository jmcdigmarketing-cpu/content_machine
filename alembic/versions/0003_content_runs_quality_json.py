"""Add content_runs.quality_json — persisted pre-publish quality scores (Pillar 1).

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns("content_runs")}
    if "quality_json" in cols:
        return
    op.add_column(
        "content_runs",
        sa.Column("quality_json", sa.Text(), server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("content_runs", "quality_json")
