from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.models.base import Base
from src.infrastructure.db.models.identity import UserORM


class ReferralORM(Base):
    """One row per referrer→referee invitation lifecycle.

    `referee_id` is UNIQUE — a user can only be referred once. That uniqueness
    is the primary anti-abuse fence: even if multiple `/start ref_<code>`
    payloads target the same user, only the first succeeds.
    """

    __tablename__ = "referrals"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    referrer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    referee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    referrer: Mapped[UserORM] = relationship(
        UserORM, foreign_keys=[referrer_id]
    )
    referee: Mapped[UserORM] = relationship(UserORM, foreign_keys=[referee_id])
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_created: Mapped[bool] = mapped_column(
        server_default="false", nullable=False
    )
    first_rating_given: Mapped[bool] = mapped_column(
        server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
