"""add SEED to the role enum

Marks seeded content users (scripts/seed_profiles.py) so they can be told
apart from real people — nothing is ever delivered to their telegram_id.

Postgres cannot drop a value from an enum, so the downgrade rebuilds the
type; any row still holding SEED is moved to USER first.

Revision ID: e5c1b73f9a28
Revises: d3a9c5b71e42
Create Date: 2026-07-23 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5c1b73f9a28"
down_revision: Union[str, Sequence[str], None] = "d3a9c5b71e42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'SEED'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'USER' WHERE role = 'SEED'")
    op.execute("ALTER TYPE role RENAME TO role_old")
    op.execute("CREATE TYPE role AS ENUM ('USER', 'ADMIN')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE role USING role::text::role"
    )
    op.execute("DROP TYPE role_old")
