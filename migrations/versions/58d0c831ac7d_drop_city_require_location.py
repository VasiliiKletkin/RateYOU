"""drop profiles.city + ALTER location SET NOT NULL

Revision ID: 58d0c831ac7d
Revises: 80b891a30054
Create Date: 2026-05-12 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from geoalchemy2 import Geography

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "58d0c831ac7d"
down_revision: Union[str, Sequence[str], None] = "80b891a30054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Location is now mandatory. Profiles created before the geo feature
    # exist with location IS NULL — purge them so SET NOT NULL succeeds.
    # `profile_photos` rows cascade-delete via the FK.
    op.execute("DELETE FROM profiles WHERE location IS NULL")
    op.alter_column("profiles", "location", nullable=False)
    op.drop_column("profiles", "city")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("city", sa.String(length=100), nullable=False, server_default=""),
    )
    op.alter_column("profiles", "city", server_default=None)
    op.alter_column(
        "profiles",
        "location",
        existing_type=Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
