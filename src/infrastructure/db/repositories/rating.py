from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.rating.entities import Rating
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.value_objects import RatingId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.rating import (
    orm_to_rating,
    orm_to_summary,
    rating_to_orm,
    summary_to_orm,
)
from src.infrastructure.db.models.rating import ProfileScoreSummaryORM, RatingORM


@dataclass
class RatingRepository:
    session: AsyncSession

    async def add(self, rating: Rating) -> None:
        self.session.add(rating_to_orm(rating))
        await self.session.flush()

    async def get_by_id(self, rating_id: RatingId) -> Rating | None:
        result = await self.session.execute(
            select(RatingORM).where(RatingORM.id == rating_id.value)
        )
        orm = result.scalar_one_or_none()
        return orm_to_rating(orm) if orm is not None else None

    async def get_by_rater_and_rated(
        self,
        rater_id: UserId,
        rated_id: UserId,
    ) -> Rating | None:
        result = await self.session.execute(
            select(RatingORM).where(
                RatingORM.rater_id == rater_id.value,
                RatingORM.rated_id == rated_id.value,
            )
        )
        orm = result.scalar_one_or_none()
        return orm_to_rating(orm) if orm is not None else None

    async def update(self, rating: Rating) -> None:
        existing = await self.session.get(RatingORM, rating.id.value)
        if existing is None:
            raise ValueError(f"Rating {rating.id.value} not found for update")
        existing.score = rating.score.value
        existing.updated_at = rating.updated_at
        await self.session.flush()

    async def delete(self, rating: Rating) -> None:
        existing = await self.session.get(RatingORM, rating.id.value)
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        result = await self.session.execute(
            select(
                func.avg(RatingORM.score),
                func.count(RatingORM.id),
            ).where(RatingORM.rated_id == rated_id.value)
        )
        avg_raw, count_raw = result.one()
        avg = float(avg_raw) if avg_raw is not None else 0.0
        count = int(count_raw)
        return avg, count


@dataclass
class ProfileScoreSummaryRepository:
    session: AsyncSession

    async def upsert(self, summary: ProfileScoreSummary) -> None:
        existing = await self.session.get(ProfileScoreSummaryORM, summary.rated_id.value)
        if existing is None:
            self.session.add(summary_to_orm(summary))
        else:
            existing.average_score = summary.average_score
            existing.rating_count = summary.rating_count
            existing.updated_at = summary.updated_at
        await self.session.flush()

    async def get(self, rated_id: UserId) -> ProfileScoreSummary | None:
        orm = await self.session.get(ProfileScoreSummaryORM, rated_id.value)
        return orm_to_summary(orm) if orm is not None else None
