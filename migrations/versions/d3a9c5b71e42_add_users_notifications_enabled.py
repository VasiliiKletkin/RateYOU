"""add users.notifications_enabled

Opt-out switch for bot-initiated broadcasts, toggled from /settings.
Defaults to true so existing users keep receiving nudges until they say
otherwise; server_default is what backfills the already-present rows.

Revision ID: d3a9c5b71e42
Revises: c2f7a1d4e8b3
Create Date: 2026-07-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3a9c5b71e42"
down_revision: Union[str, Sequence[str], None] = "c2f7a1d4e8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled")
