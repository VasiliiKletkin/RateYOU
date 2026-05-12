"""add users.language

Revision ID: e9f4c5d8a1b2
Revises: d7b3e8a1c2f0
Create Date: 2026-05-12 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e9f4c5d8a1b2"
down_revision: Union[str, Sequence[str], None] = "d7b3e8a1c2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Server default backfills existing rows with "en"; the bot updates each
    # user's stored language the next time they hit /start (or any other
    # handler that calls RegisterUserUseCase with a normalised code).
    op.add_column(
        "users",
        sa.Column(
            "language",
            sa.String(length=8),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
