from uuid import UUID

from geoalchemy2 import Geography, WKBElement
from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.discovery.value_objects import GenderPreference
from src.infrastructure.db.models.base import Base, CreatedAtMixin, UpdatedAtMixin


class SearchPreferencesORM(Base, CreatedAtMixin, UpdatedAtMixin):
    """Per-user feed preferences. 1:1 with users."""

    __tablename__ = "search_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    gender_preference: Mapped[GenderPreference] = mapped_column(
        Enum(GenderPreference), default=GenderPreference.ANY
    )
    min_rating: Mapped[int] = mapped_column(default=0)
    # Origin the feed sorts around. Nullable: a fresh prefs row has no search
    # area until the user sets one (or it's seeded from their profile).
    location: Mapped[WKBElement | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), default=None
    )
