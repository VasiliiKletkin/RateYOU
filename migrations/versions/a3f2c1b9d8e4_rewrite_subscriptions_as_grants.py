"""rewrite subscriptions as a grant ledger

Drops the single-row-per-user `subscriptions` table and replaces it with
`subscription_grants`, where each granted period of premium days (purchase,
bonus, ...) is its own row. The user's current premium state is derived by
projecting their grants — there is no UNIQUE on `owner_id` anymore.

Pre-production: no data to preserve.

Revision ID: a3f2c1b9d8e4
Revises: e9f4c5d8a1b2
Create Date: 2026-05-12 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f2c1b9d8e4'
down_revision: Union[str, Sequence[str], None] = 'e9f4c5d8a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('subscriptions')
    op.create_table(
        'subscription_grants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('tier', sa.String(length=16), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('transaction_id', sa.Uuid(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'is_revoked',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['transaction_id'], ['transactions.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_subscription_grants_owner_expires',
        'subscription_grants',
        ['owner_id', 'expires_at'],
    )
    op.create_index(
        'ix_subscription_grants_transaction',
        'subscription_grants',
        ['transaction_id'],
        unique=True,
        postgresql_where=sa.text('transaction_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'ix_subscription_grants_transaction', table_name='subscription_grants'
    )
    op.drop_index(
        'ix_subscription_grants_owner_expires', table_name='subscription_grants'
    )
    op.drop_table('subscription_grants')
    op.create_table(
        'subscriptions',
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('tier', sa.String(length=16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'is_revoked',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('owner_id'),
    )
