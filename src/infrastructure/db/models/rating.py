from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.models.base import Base, CreatedAtMixin, UpdatedAtMixin
from src.infrastructure.db.models.identity import UserORM


class RatingORM(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("rater_id", "rated_id", name="uq_ratings_rater_rated"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rater_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rated_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Admin-only conveniences: two FKs to users need explicit foreign_keys
    # (same pattern as ReferralORM). The bot-side repository never touches
    # these, so no lazy-load can fire in the async request path.
    rater: Mapped[UserORM] = relationship(UserORM, foreign_keys=[rater_id])
    rated: Mapped[UserORM] = relationship(UserORM, foreign_keys=[rated_id])
    score: Mapped[int]


class ProfileScoreSummaryORM(Base, UpdatedAtMixin):
    __tablename__ = "profile_score_summaries"

    rated_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    average_score: Mapped[float]
    rating_count: Mapped[int]
