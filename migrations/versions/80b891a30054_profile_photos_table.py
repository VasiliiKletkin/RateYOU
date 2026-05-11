"""profile_photos table + drop profiles.photo_file_id

Revision ID: 80b891a30054
Revises: e7097374101e
Create Date: 2026-05-12 01:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "80b891a30054"
down_revision: Union[str, Sequence[str], None] = "e7097374101e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table — owner-driven photo list. Position is 0-based; reconciler
    # in `ProfileRepository.update` rewrites positions on every save.
    op.create_table(
        "profile_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_id", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "profile_id", "position", name="uq_profile_photos_position"
        ),
    )
    op.create_index(
        "ix_profile_photos_profile_id", "profile_photos", ["profile_id"]
    )

    # Backfill: every existing profile gets one photo row at position 0
    # carrying its old photo_file_id. Uses gen_random_uuid() (pgcrypto, which
    # PostGIS pulls in transitively, or built-in on PG 13+).
    op.execute(
        """
        INSERT INTO profile_photos (id, profile_id, file_id, position)
        SELECT gen_random_uuid(), id, photo_file_id, 0
        FROM profiles
        WHERE photo_file_id IS NOT NULL
        """
    )

    op.drop_column("profiles", "photo_file_id")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("photo_file_id", sa.String(length=500), nullable=True),
    )
    op.execute(
        """
        UPDATE profiles p
        SET photo_file_id = pp.file_id
        FROM profile_photos pp
        WHERE pp.profile_id = p.id AND pp.position = 0
        """
    )
    op.alter_column("profiles", "photo_file_id", nullable=False)
    op.drop_index("ix_profile_photos_profile_id", table_name="profile_photos")
    op.drop_table("profile_photos")
