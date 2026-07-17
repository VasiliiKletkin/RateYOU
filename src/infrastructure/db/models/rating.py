from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.models.base import Base, CreatedAtMixin, UpdatedAtMixin


class RatingORM(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("rater_id", "rated_id", name="uq_ratings_rater_rated"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rater_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rated_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[int]


class ProfileScoreSummaryORM(Base, UpdatedAtMixin):
    __tablename__ = "profile_score_summaries"

    rated_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    average_score: Mapped[float]
    rating_count: Mapped[int]
