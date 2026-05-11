from dataclasses import dataclass
from datetime import datetime

from src.domain.rating.entities import Rating
from src.domain.rating.repositories import IRatingRepository
from src.domain.rating.value_objects import Score
from src.domain.shared.identifiers import UserId


@dataclass
class RatingFulfillmentService:
    """Encapsulates the create-or-update Rating policy.

    Domain service: owns the lifecycle of the Rating aggregate but does NOT
    update the `ProfileScoreSummary` — that's reactive, driven by the
    `RatingGiven` / `RatingWithdrawn` events the aggregate emits.
    """

    rating_repo: IRatingRepository

    async def rate(
        self,
        rater_id: UserId,
        rated_id: UserId,
        score: Score,
        now: datetime,
    ) -> Rating:
        existing = await self.rating_repo.get_by_rater_and_rated(rater_id, rated_id)
        if existing is None:
            rating = Rating.give(rater_id, rated_id, score, now)
            await self.rating_repo.add(rating)
            return rating
        existing.change_score(score, now)
        await self.rating_repo.update(existing)
        return existing

    async def withdraw(
        self,
        rater_id: UserId,
        rated_id: UserId,
        now: datetime,
    ) -> Rating | None:
        rating = await self.rating_repo.get_by_rater_and_rated(rater_id, rated_id)
        if rating is None:
            return None
        rating.withdraw(now)
        await self.rating_repo.delete(rating)
        return rating
