"""Drop tags.is_protected (removed from the plan; anyone may move a tag).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("tags", "is_protected")


def downgrade() -> None:
    op.add_column(
        "tags",
        sa.Column("is_protected", sa.Boolean(), server_default="false", nullable=False),
    )
