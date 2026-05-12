"""create referrals table

Append-only ledger of paid-out referrals (one row per successful invite,
i.e. when the referee created their profile and both parties received
their BONUS Subscription). UNIQUE on `referee_id` is the primary
anti-abuse fence: each user can be referred at most once.

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
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
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


def downgrade() -> None:
    op.drop_index('ix_referrals_referrer_id', table_name='referrals')
    op.drop_table('referrals')
