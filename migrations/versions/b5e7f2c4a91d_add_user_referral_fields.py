"""add user referral fields

Adds `referred_by_user_id` to the `users` table (self-FK marking who
invited this user via a `/start <referrer_telegram_id>` deep link).
The user's own referral handle is just their `telegram_id` — no
separate code column.

Revision ID: b5e7f2c4a91d
Revises: a3f2c1b9d8e4
Create Date: 2026-05-12 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e7f2c4a91d'
down_revision: Union[str, Sequence[str], None] = 'a3f2c1b9d8e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('referred_by_user_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_users_referred_by',
        'users',
        'users',
        ['referred_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_referred_by', 'users', type_='foreignkey')
    op.drop_column('users', 'referred_by_user_id')
