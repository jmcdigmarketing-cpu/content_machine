"""Add thumbnail_scores table for pre-publish CTR correlation.

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "thumbnail_scores" in inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "thumbnail_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content_run_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=64), server_default="default"),
        sa.Column("image_path", sa.String(length=1024), server_default=""),
        sa.Column("topic", sa.String(length=512), server_default=""),
        sa.Column("curiosity", sa.Float(), server_default="0"),
        sa.Column("clarity", sa.Float(), server_default="0"),
        sa.Column("contrast", sa.Float(), server_default="0"),
        sa.Column("emotion", sa.Float(), server_default="0"),
        sa.Column("overall", sa.Float(), server_default="0"),
        sa.Column("suggestions_json", sa.Text(), server_default="[]"),
        sa.Column("source", sa.String(length=16), server_default="heuristic"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["content_run_id"],
            ["content_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_thumbnail_scores_content_run_id",
        "thumbnail_scores",
        ["content_run_id"],
    )
    op.create_index(
        "ix_thumbnail_scores_channel_id",
        "thumbnail_scores",
        ["channel_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_thumbnail_scores_channel_id", table_name="thumbnail_scores")
    op.drop_index(
        "ix_thumbnail_scores_content_run_id", table_name="thumbnail_scores"
    )
    op.drop_table("thumbnail_scores")
