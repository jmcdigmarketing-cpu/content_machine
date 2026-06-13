"""Baseline schema — matches storage/models.py (pre feature migrations).

Revision ID: 0001
Revises:
Create Date: 2026-06-04

Existing databases: stamp this revision after verify, then use upgrade for later revisions:

    alembic stamp 0001
"""

from typing import Sequence, Union

from alembic import op

from storage.models import Base

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all Content OS tables if missing (same as py -m storage.init_db)."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all Content OS tables (destructive — dev/test only)."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
