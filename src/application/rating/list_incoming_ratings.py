from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.rating.dto import IncomingRatingItem, IncomingRatingsResponse
from src.domain.identity.repositories import IUserRepository
from src.domain.rating.repositories import IRatingRepository
from src.domain.shared.exceptions import PremiumRequired
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionStatus
from src.domain.subscription.repositories import ISubscriptionRepository

DEFAULT_LIMIT = 10


@dataclass
class ListIncomingRatingsUseCase:
    """Premium-gated read: who recently rated me.

    Raises `PremiumRequired` if the viewer has no active subscription.

    Deliberately does NOT touch the Profile context: raters may not have a
    profile at all (browsing needs only a search location), so the rater is
    identified purely by their User — the cached `@username` when they have
    one, plus their `telegram_id` so the bot can still render a clickable
    mention for the (many) accounts without a handle.
    """

    subscription_repo: ISubscriptionRepository
    rating_repo: IRatingRepository
    user_repo: IUserRepository

    async def execute(
        self,
        viewer_id: UUID,
        limit: int = DEFAULT_LIMIT,
    ) -> IncomingRatingsResponse:
        viewer = UserId(viewer_id)

        grants = await self.subscription_repo.list_for(viewer)
        if not SubscriptionStatus.from_grants(grants, datetime.now(UTC)).is_active:
            raise PremiumRequired

        ratings = await self.rating_repo.list_for_rated(viewer, limit)

        items: list[IncomingRatingItem] = []
        for rating in ratings:
            rater = await self.user_repo.get_by_id(rating.rater_id)
            items.append(
                IncomingRatingItem(
                    score=rating.score.value,
                    rated_at=rating.created_at,
                    rater_username=rater.username if rater is not None else None,
                    rater_telegram_id=rater.telegram_id.value if rater is not None else None,
                )
            )

        return IncomingRatingsResponse(items=tuple(items))
