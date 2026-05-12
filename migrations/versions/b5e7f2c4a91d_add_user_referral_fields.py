"""add user referral fields

Adds `referral_code` (unique, 8-char base62) and `referred_by_user_id` to
the `users` table. Existing rows get a random server-generated code so the
NOT NULL + UNIQUE constraints can be applied immediately.

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
    # 1. Add nullable referral_code first so existing rows survive the ALTER.
    op.add_column(
        'users',
        sa.Column('referral_code', sa.String(length=8), nullable=True),
    )
    # 2. Backfill existing rows. 8 hex chars from md5 is a base16 substring —
    #    a strict subset of base62, so values are valid `ReferralCode`s when
    #    later mapped back into the domain.
    op.execute(
        "UPDATE users "
        "SET referral_code = substring(md5(random()::text || id::text), 1, 8) "
        "WHERE referral_code IS NULL"
    )
    # 3. Lock in NOT NULL + UNIQUE.
    op.alter_column('users', 'referral_code', nullable=False)
    op.create_unique_constraint(
        'uq_users_referral_code', 'users', ['referral_code']
    )
    # 4. Self-referencing FK for the inviter. SET NULL on delete so deleting
    #    a referrer doesn't cascade-delete their referees.
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
    op.drop_constraint('uq_users_referral_code', 'users', type_='unique')
    op.drop_column('users', 'referral_code')
