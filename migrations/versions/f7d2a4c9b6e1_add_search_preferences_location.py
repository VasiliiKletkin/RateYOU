"""add search_preferences.location

The feed now sorts candidates by distance from a per-user *search* origin
instead of the viewer's own profile, so a user can browse without a profile
of their own. Backfills existing rows from the matching profile's location
so already-onboarded users don't lose their feed.

Revision ID: f7d2a4c9b6e1
Revises: e5c1b73f9a28
Create Date: 2026-07-31 12:00:00.000000

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "f7d2a4c9b6e1"
down_revision: Union[str, Sequence[str], None] = "e5c1b73f9a28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "search_preferences",
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
    )
    # Seed the search origin from the user's own profile where they have one,
    # so existing profiled users keep a working feed without re-entering a city.
    op.execute(
        "UPDATE search_preferences AS sp "
        "SET location = p.location "
        "FROM profiles AS p "
        "WHERE p.owner_id = sp.user_id AND sp.location IS NULL"
    )


def downgrade() -> None:
    op.drop_column("search_preferences", "location")
