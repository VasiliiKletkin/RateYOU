from uuid import UUID

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
