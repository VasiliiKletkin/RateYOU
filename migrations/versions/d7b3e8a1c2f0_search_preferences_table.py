"""create search_preferences, migrate gender_preference off profiles

Revision ID: d7b3e8a1c2f0
Revises: c4a1f2e7b9d3
Create Date: 2026-05-12 15:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d7b3e8a1c2f0"
down_revision: Union[str, Sequence[str], None] = "c4a1f2e7b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "gender_preference",
            sa.String(length=16),
            nullable=False,
            server_default="any",
        ),
        sa.Column(
            "min_rating", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Backfill existing profiles' gender_preference into the new table.
    # Users without a profile don't get a row — /create or /settings will
    # create one on first use.
    op.execute(
        """
        INSERT INTO search_preferences
            (user_id, gender_preference, min_rating, created_at, updated_at)
        SELECT
            owner_id, gender_preference, 0, NOW(), NOW()
        FROM profiles
        """
    )

    op.drop_column("profiles", "gender_preference")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "gender_preference",
            sa.String(length=16),
            nullable=False,
            server_default="any",
        ),
    )
    # Restore values from search_preferences where possible.
    op.execute(
        """
        UPDATE profiles p
        SET gender_preference = sp.gender_preference
        FROM search_preferences sp
        WHERE p.owner_id = sp.user_id
        """
    )
    op.drop_table("search_preferences")
