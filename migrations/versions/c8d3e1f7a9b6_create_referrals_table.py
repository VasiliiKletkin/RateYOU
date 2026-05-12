"""create referrals table

Tracks one referrer→referee invitation lifecycle (PENDING → QUALIFIED →
REWARDED). UNIQUE on `referee_id` is the primary anti-abuse fence: each
user can only be referred once, regardless of how many `/start ref_<code>`
payloads target them.

Revision ID: c8d3e1f7a9b6
Revises: b5e7f2c4a91d
Create Date: 2026-05-12 19:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d3e1f7a9b6'
down_revision: Union[str, Sequence[str], None] = 'b5e7f2c4a91d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'referrals',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('referrer_id', sa.Uuid(), nullable=False),
        sa.Column('referee_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column(
            'profile_created',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
        sa.Column(
            'first_rating_given',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('qualified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rewarded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['referrer_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['referee_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referee_id', name='uq_referrals_referee_id'),
    )
    op.create_index(
        'ix_referrals_referrer_id', 'referrals', ['referrer_id']
    )
    op.create_index(
        'ix_referrals_status', 'referrals', ['status']
    )


def downgrade() -> None:
    op.drop_index('ix_referrals_status', table_name='referrals')
    op.drop_index('ix_referrals_referrer_id', table_name='referrals')
    op.drop_table('referrals')
