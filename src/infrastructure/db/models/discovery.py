from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.discovery.value_objects import GenderPreference
from src.infrastructure.db.models.base import Base


class SearchPreferencesORM(Base):
    """Per-user feed preferences. 1:1 with users."""

    __tablename__ = "search_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    gender_preference: Mapped[GenderPreference] = mapped_column(
        Enum(GenderPreference), default=GenderPreference.ANY
    )
    min_rating: Mapped[int] = mapped_column(server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
