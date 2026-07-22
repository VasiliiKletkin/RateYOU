"""add users.username

Caches the Telegram handle so /my_ratings can offer a way to contact a rater.
Nullable because a large share of Telegram accounts have no username; the
value is refreshed on every /start since users can change or drop it.

Revision ID: c2f7a1d4e8b3
Revises: b1e692424df8
Create Date: 2026-07-20 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2f7a1d4e8b3"
down_revision: Union[str, Sequence[str], None] = "b1e692424df8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "username")
