from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.rating.entities import Rating
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.value_objects import RatingId, Score
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.rating import ProfileScoreSummaryORM, RatingORM


@dataclass
class RatingRepository:
    session: AsyncSession

    async def add(self, rating: Rating) -> None:
        self.session.add(
            RatingORM(
                id=rating.id.value,
                rater_id=rating.rater_id.value,
                rated_id=rating.rated_id.value,
                score=rating.score.value,
                created_at=rating.created_at,
                updated_at=rating.updated_at,
            )
        )
        await self.session.flush()

    async def get_by_id(self, rating_id: RatingId) -> Rating | None:
        result = await self.session.execute(
            select(RatingORM).where(RatingORM.id == rating_id.value)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return Rating(
            id=RatingId(orm.id),
            rater_id=UserId(orm.rater_id),
            rated_id=UserId(orm.rated_id),
            score=Score(orm.score),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

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
        if orm is None:
            return None
        return Rating(
            id=RatingId(orm.id),
            rater_id=UserId(orm.rater_id),
            rated_id=UserId(orm.rated_id),
            score=Score(orm.score),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

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

    async def list_rater_ids_active_since(self, since: datetime) -> list[UserId]:
        result = await self.session.execute(
            select(RatingORM.rater_id).where(RatingORM.updated_at > since).distinct()
        )
        return [UserId(rater_id) for rater_id in result.scalars()]

    async def list_for_rated(
        self,
        rated_id: UserId,
        limit: int,
    ) -> list[Rating]:
        result = await self.session.execute(
            select(RatingORM)
            .where(RatingORM.rated_id == rated_id.value)
            .order_by(RatingORM.created_at.desc())
            .limit(limit)
        )
        return [
            Rating(
                id=RatingId(orm.id),
                rater_id=UserId(orm.rater_id),
                rated_id=UserId(orm.rated_id),
                score=Score(orm.score),
                created_at=orm.created_at,
                updated_at=orm.updated_at,
            )
            for orm in result.scalars().all()
        ]


@dataclass
class ProfileScoreSummaryRepository:
    session: AsyncSession

    async def upsert(self, summary: ProfileScoreSummary) -> None:
        existing = await self.session.get(ProfileScoreSummaryORM, summary.rated_id.value)
        if existing is None:
            self.session.add(
                ProfileScoreSummaryORM(
                    rated_id=summary.rated_id.value,
                    average_score=summary.average_score,
                    rating_count=summary.rating_count,
                    updated_at=summary.updated_at,
                )
            )
        else:
            existing.average_score = summary.average_score
            existing.rating_count = summary.rating_count
            existing.updated_at = summary.updated_at
        await self.session.flush()

    async def get(self, rated_id: UserId) -> ProfileScoreSummary | None:
        orm = await self.session.get(ProfileScoreSummaryORM, rated_id.value)
        if orm is None:
            return None
        return ProfileScoreSummary(
            rated_id=UserId(orm.rated_id),
            average_score=orm.average_score,
            rating_count=orm.rating_count,
            updated_at=orm.updated_at,
        )
