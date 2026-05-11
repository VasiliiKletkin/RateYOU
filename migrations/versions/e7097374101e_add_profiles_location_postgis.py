"""add profiles.location (PostGIS Geography Point)

Revision ID: e7097374101e
Revises: 114588e01583
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from geoalchemy2 import Geography

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7097374101e"
down_revision: Union[str, Sequence[str], None] = "114588e01583"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS provides geography type + ST_Distance + GiST index support.
    # Idempotent — base image is postgis/postgis which has it preinstalled.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.add_column(
        "profiles",
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )
    # GiST index — required for efficient ST_DWithin / ORDER BY ST_Distance.
    # geoalchemy2 also auto-creates one on column add, but only inside
    # `create_table`; for add_column we declare it explicitly.
    op.create_index(
        "ix_profiles_location",
        "profiles",
        ["location"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_location", table_name="profiles")
    op.drop_column("profiles", "location")
    # Don't drop the extension — other tables in this DB might depend on it.
