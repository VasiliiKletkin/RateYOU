"""add profiles.gender_preference

Revision ID: c4a1f2e7b9d3
Revises: 58d0c831ac7d
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4a1f2e7b9d3"
down_revision: Union[str, Sequence[str], None] = "58d0c831ac7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Server default "any" backfills existing rows and matches the ORM column,
    # so feed behaviour for legacy profiles stays "show everyone" until they
    # opt in via /settings.
    op.add_column(
        "profiles",
        sa.Column(
            "gender_preference",
            sa.String(length=16),
            nullable=False,
            server_default="any",
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "gender_preference")
